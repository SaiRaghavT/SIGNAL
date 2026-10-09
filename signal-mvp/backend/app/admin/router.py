from datetime import datetime, time, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from backend.app.agents.acknowledgement.schemas import AcknowledgementRequest
from backend.app.agents.acknowledgement.service import AcknowledgementService
from backend.app.agents.audit_ledger.schemas import AuditEventCreate
from backend.app.agents.audit_ledger.service import AuditLedgerService
from backend.app.config.settings import settings
from backend.app.agents.retry_resubmission.schemas import RetryResubmissionRequest
from backend.app.agents.retry_resubmission.service import RetryResubmissionService
from backend.app.case.workflow_api import ReviewRequest, _has_immediate_reporting_rule, create_review
from backend.app.case.report_fields import available_case_report_fields
from backend.app.database import get_db
from backend.app.ecr.builder import build_ecr
from backend.app.models.audit_event import AuditEvent
from backend.app.models.case import Case
from backend.app.models.candidate import Candidate
from backend.app.models.condition import Condition
from backend.app.models.encounter import Encounter
from backend.app.models.lab_result import LabResult
from backend.app.models.patient import Patient
from backend.app.models.submissions import Submission
from backend.app.models.workflow_records import Acknowledgement, CaseWorkflowRecord, Report, SubmissionAttempt
from backend.app.schemas.validation import validate_ecr
from backend.app.submission.gates import smart_fields_for_case
from backend.app.agents.ecr_submission.schemas import ECRSubmissionRequest
from backend.app.agents.ecr_submission.service import ECRSubmissionService
from backend.app.canonical.query_service import _case_patient_id, _patient_deadline

from .schemas import (
    AdminReviewRequest,
    AdminSessionSubmissionCleanupRequest,
    BatchCreateRequest,
    QueueRequest,
)

router = APIRouter(prefix="/api/admin", tags=["Administrator"])
audit = AuditLedgerService()
ACTIVE_QUEUE_STATUSES = {"QUEUED", "READY_FOR_SUBMISSION"}


def _is_active_queue_status(status: str | None) -> bool:
    return (status or "").strip().upper() in ACTIVE_QUEUE_STATUSES


def _latest(db: Session, case_id: str, kind: str) -> CaseWorkflowRecord | None:
    return (db.query(CaseWorkflowRecord)
            .filter(CaseWorkflowRecord.case_id == case_id, CaseWorkflowRecord.record_type == kind)
            .order_by(CaseWorkflowRecord.created_at.desc()).first())


def _event(db: Session, entity_type: str, entity_id: str, kind: str, actor: str, data: dict) -> None:
    audit.record_event(AuditEventCreate(
        entity_type=entity_type, entity_id=entity_id, event_type=kind,
        actor_type="USER", actor_id=actor, source_agent="admin_api",
        status="SUCCESS", new_value=data, workflow_stage="ADMIN",
    ), db)


def _case(db: Session, case_id: str) -> Case:
    try:
        parsed = UUID(case_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="case_id must be a UUID.") from exc
    row = db.query(Case).filter(Case.case_id == parsed).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Case not found.")
    return row


def _validation(case: Case) -> dict:
    result = validate_ecr(build_ecr(case), smart_fields_for_case(case))
    return {"valid": result.valid, "errors": result.errors,
            "missing_information": list(result.completion_required), "warnings": result.warnings}


def _persist_case_deadline_priority(db: Session, case: Case) -> None:
    """Resolve the case deadline from canonical clinical evidence and its reporting rule."""
    patient_id = _case_patient_id(case)
    if patient_id is None:
        return
    patient = db.query(Patient).filter(Patient.patient_id == patient_id).first()
    if patient is None:
        return

    conditions = db.query(Condition).filter(Condition.patient_id == patient_id).all()
    lab_results = db.query(LabResult).filter(LabResult.patient_id == patient_id).all()
    last_encounter = db.query(
        func.max(func.coalesce(Encounter.end_time, Encounter.start_time))
    ).filter(
        Encounter.patient_id == patient_id,
        func.coalesce(Encounter.end_time, Encounter.start_time).isnot(None),
    ).scalar()
    candidate = db.query(Candidate).filter(Candidate.candidate_id == case.candidate_id).first()

    deadline_data, _reason = _patient_deadline(
        patient=patient,
        conditions=conditions,
        lab_results=lab_results,
        candidate=candidate,
        case=case,
        last_encounter=last_encounter,
    )
    if not deadline_data or deadline_data.get("status") == "NO_RULE":
        # A stale placeholder such as NO_RULE_AVAILABLE should not prevent the
        # configured jurisdiction/disease catalog rule from being resolved.
        from copy import copy

        case_without_placeholder_rule = copy(case)
        case_without_placeholder_rule.rule_id = None
        deadline_data, _reason = _patient_deadline(
            patient=patient,
            conditions=conditions,
            lab_results=lab_results,
            candidate=candidate,
            case=case_without_placeholder_rule,
            last_encounter=last_encounter,
        )

    if not deadline_data:
        return
    changed = False
    resolved_deadline = deadline_data.get("deadline")
    resolved_priority = deadline_data.get("urgency")
    if resolved_deadline is not None and case.deadline != resolved_deadline:
        case.deadline = resolved_deadline
        changed = True
    if not case.severity and resolved_priority:
        case.severity = resolved_priority
        changed = True
    if changed:
        db.commit()


def _condition_display(case: Case) -> str | None:
    """Prefer the stored human-readable diagnosis for Admin display."""
    clinical_evidence = case.clinical_evidence or {}
    diagnosis = clinical_evidence.get("diagnosis")
    if isinstance(diagnosis, str) and diagnosis.strip() and "|" not in diagnosis:
        return diagnosis.strip()

    disease = case.disease
    if disease and disease.rsplit("|", 1)[-1] == "14189004":
        return "Measles"
    return disease


def _submission_mode(case: Case, queue: CaseWorkflowRecord | None = None) -> str:
    if _has_immediate_reporting_rule(case):
        return "IMMEDIATE"
    report_fields = case.report_fields if isinstance(case.report_fields, dict) else {}
    payload = queue.payload if queue and isinstance(queue.payload, dict) else {}
    raw_mode = case.submission_mode or payload.get("submission_mode") or report_fields.get("submission_mode")
    normalized = str(raw_mode or "INDIVIDUAL").strip().replace("-", "_").replace(" ", "_").upper()
    if normalized in {"PER_CASE", "PERCASE"}:
        return "INDIVIDUAL"
    if normalized in {"IMMEDIATE", "INDIVIDUAL", "BATCH"}:
        return normalized
    return "INDIVIDUAL" if queue and _is_active_queue_status(queue.status) else ""


def _case_payload(db: Session, case: Case) -> dict:
    _persist_case_deadline_priority(db, case)
    case_id = str(case.case_id)
    queue = _latest(db, case_id, "ADMIN_QUEUE")
    review = _latest(db, case_id, "REVIEW")
    attestation = _latest(db, case_id, "ATTESTATION")
    demo_simulation = _latest(db, case_id, "ADMIN_DEMO_SUBMISSION")
    validation = _validation(case)
    demo_submission = bool(queue and (queue.payload or {}).get("demo_submission"))
    report = (db.query(Report).filter(Report.case_id == case_id, Report.status == "GENERATED")
              .order_by(Report.created_at.desc()).first())
    submission = (db.query(Submission).filter(Submission.case_id == case_id)
                  .order_by(Submission.created_at.desc()).first())
    latest_submission = submission.status if submission else None
    queued = bool(queue and _is_active_queue_status(queue.status))
    submission_mode = _submission_mode(case, queue)
    return {
        "case_id": case_id, "patient": case.patient or {}, "condition": _condition_display(case),
        "jurisdiction": case.jurisdiction, "deadline": case.deadline, "priority": case.severity,
        "case_status": case.status, "reportability": case.reportability_decision,
        "review_status": review.status if review else "PENDING",
        "attestation_status": attestation.status if attestation else "PENDING",
        "submission_mode": submission_mode,
        "queue_status": queue.status if queue else "NOT_QUEUED",
        "demo_submission": demo_submission,
        "demo_simulation_available": bool(settings.demo_queue_enabled),
        "demo_simulation_status": demo_simulation.status if demo_simulation else None,
        "demo_submission_record_id": demo_simulation.record_id if demo_simulation else None,
        "demo_submission_created_at": demo_simulation.created_at if demo_simulation else None,
        "submission_status": latest_submission,
        "missing_information": validation["missing_information"],
        "available_actions": (["review"] if review is None or review.status != "APPROVE" else [])
            + (["dispatch"] if queued and not demo_submission and report and validation["valid"] and attestation and attestation.status == "ATTESTED" else [])
            + (["retry"] if latest_submission in {"FAILED", "ERROR", "REJECTED"} else []),
        "report_id": report.report_id if report else None,
        "submission_id": submission.submission_id if submission else None,
    }


def _case_detail_payload(db: Session, case: Case) -> dict:
    """Add stored case evidence to the detail response without expanding queue rows."""
    case_id = UUID(str(case.case_id))
    review = _latest(db, str(case_id), "REVIEW")
    attestation = _latest(db, str(case_id), "ATTESTATION")
    validation = _validation(case)
    return {
        **_case_payload(db, case),
        "severity": case.severity,
        "rule_id": case.rule_id,
        "clinical_evidence": case.clinical_evidence or {},
        "laboratory_evidence": case.laboratory_evidence or [],
        "ai_evidence": case.ai_evidence or {},
        "report_fields": available_case_report_fields(case),
        "validation": validation,
        "review": ({"status": review.status, "payload": review.payload, "created_at": review.created_at} if review else None),
        "attestation": ({"status": attestation.status, "payload": attestation.payload, "created_at": attestation.created_at} if attestation else None),
    }


def _eligible_for_dispatch(db: Session, case: Case) -> None:
    queue = _latest(db, str(case.case_id), "ADMIN_QUEUE")
    if queue is not None and (queue.payload or {}).get("demo_submission"):
        raise HTTPException(status_code=409, detail="Synthetic demo queue entries cannot be dispatched externally.")
    case.submission_mode = _submission_mode(case, queue)
    payload = _case_payload(db, case)
    if not _is_active_queue_status(payload["queue_status"]):
        raise HTTPException(status_code=409, detail="Case is not queued for Admin dispatch.")
    if payload["review_status"] != "APPROVE":
        raise HTTPException(status_code=409, detail="An approved review is required before dispatch.")
    if payload["attestation_status"] != "ATTESTED":
        raise HTTPException(status_code=409, detail="A persisted attestation is required before dispatch.")
    if not payload["report_id"]:
        raise HTTPException(status_code=409, detail="A generated report is required before dispatch.")
    if payload["missing_information"]:
        raise HTTPException(status_code=409, detail={"message": "Reporting package is incomplete.", "missing_information": payload["missing_information"]})


@router.get("/dashboard")
def admin_dashboard(db: Session = Depends(get_db)) -> dict:
    cases = db.query(Case).all()
    today = datetime.now(timezone.utc).date()
    due_soon = today + timedelta(days=3)
    counts = {"ready_for_submission": 0, "immediate_reports": 0, "individual_reports": 0,
              "dispatched_reports": 0, "completed_submissions": 0,
              "pending_batches": 0, "submitted_today": 0, "awaiting_acknowledgement": 0,
              "failed": 0, "retry_required": 0, "overdue": 0, "due_today": 0, "due_soon": 0}
    for case in cases:
        payload = _case_payload(db, case)
        if _is_active_queue_status(payload["queue_status"]):
            key = {"IMMEDIATE": "immediate_reports", "INDIVIDUAL": "individual_reports"}.get(payload["submission_mode"])
            if key:
                counts["ready_for_submission"] += 1
                counts[key] += 1
        elif payload["queue_status"] == "DISPATCHED":
            counts["dispatched_reports"] += 1
        deadline = case.deadline
        if deadline is not None:
            date_value = deadline.astimezone(timezone.utc).date() if deadline.tzinfo else deadline.date()
            submitted = db.query(Submission.submission_id).filter(Submission.case_id == str(case.case_id), Submission.status.in_(("SUBMITTED", "ACKNOWLEDGED"))).first()
            if not submitted:
                if date_value < today: counts["overdue"] += 1
                elif date_value == today: counts["due_today"] += 1
                elif date_value <= due_soon: counts["due_soon"] += 1
    batches = db.query(CaseWorkflowRecord).filter(CaseWorkflowRecord.record_type == "ADMIN_BATCH", CaseWorkflowRecord.status == "PENDING").count()
    counts["pending_batches"] = batches
    counts["completed_submissions"] = (
        db.query(Submission.case_id)
        .filter(Submission.status == "ACKNOWLEDGED")
        .distinct()
        .count()
    )
    start = datetime.combine(today, time.min, tzinfo=timezone.utc)
    counts["submitted_today"] = db.query(Submission.submission_id).filter(Submission.created_at >= start, Submission.status.in_(("SUBMITTED", "ACKNOWLEDGED"))).count()
    counts["awaiting_acknowledgement"] = db.query(Submission.submission_id).filter(Submission.status == "SUBMITTED").count()
    counts["failed"] = db.query(Submission.submission_id).filter(Submission.status.in_(("FAILED", "ERROR", "REJECTED"))).count()
    counts["retry_required"] = db.query(Submission.submission_id).filter(Submission.status.in_(("FAILED", "ERROR", "REJECTED"))).count()
    return counts


@router.get("/queue")
def admin_queue(db: Session = Depends(get_db)) -> dict:
    rows = []
    for case in db.query(Case).order_by(Case.deadline.asc().nullslast()).all():
        queue = _latest(db, str(case.case_id), "ADMIN_QUEUE")
        if queue and _is_active_queue_status(queue.status):
            payload = _case_payload(db, case)
            if payload.get("submission_mode") != "BATCH":
                rows.append(payload)
    return {"items": rows, "total": len(rows)}


@router.get("/queue/{case_id}")
def admin_queue_case(case_id: str, db: Session = Depends(get_db)) -> dict:
    return _case_detail_payload(db, _case(db, case_id))


@router.post("/cases/{case_id}/demo-dispatch")
def admin_demo_dispatch(case_id: str, actor_id: str = "admin", db: Session = Depends(get_db)) -> dict:
    """Persist an Admin local simulation without creating or sending a submission."""
    if not settings.demo_queue_enabled:
        raise HTTPException(status_code=403, detail="Local submission simulation is disabled.")
    case = _case(db, case_id)
    case_key = str(case.case_id)
    queue = _latest(db, case_key, "ADMIN_QUEUE")
    if queue is None:
        raise HTTPException(status_code=409, detail="This case has no persisted Admin queue entry.")
    existing = _latest(db, case_key, "ADMIN_DEMO_SUBMISSION")
    if existing is not None and existing.status == "SIMULATED":
        if queue.status in ACTIVE_QUEUE_STATUSES:
            queue.status = "DISPATCHED"
            queue.payload = {
                **(queue.payload or {}),
                "submission_id": existing.record_id,
                "status": "SIMULATED",
            }
            db.commit()
        return {
            "case_id": case_key,
            "record_id": existing.record_id,
            "status": existing.status,
            "demo_submission": True,
            "externally_dispatched": False,
        }
    if not _is_active_queue_status(queue.status):
        raise HTTPException(status_code=409, detail="This case is not active in the Admin queue.")

    payload = {
        "demo_submission": True,
        "authorization_status": "AUTHORIZED",
        "destination": "DEMO_SIMULATION",
        "externally_dispatched": False,
        "notice": "Local simulated submission recorded. No report was sent to a public health authority.",
    }
    row = CaseWorkflowRecord(
        case_id=case_key,
        record_type="ADMIN_DEMO_SUBMISSION",
        status="SIMULATED",
        actor_id=actor_id,
        payload=payload,
    )
    db.add(row)
    queue.status = "DISPATCHED"
    queue.payload = {
        **(queue.payload or {}),
        "submission_id": row.record_id,
        "status": "SIMULATED",
    }
    db.commit()
    db.refresh(row)
    _event(db, "CASE", case_key, "ADMIN_DEMO_SUBMISSION_SIMULATED", actor_id, payload)
    return {
        "case_id": case_key,
        "record_id": row.record_id,
        "status": row.status,
        "demo_submission": True,
        "externally_dispatched": False,
    }


@router.post("/queue/{case_id}/review")
def admin_review(case_id: str, request: AdminReviewRequest, db: Session = Depends(get_db)) -> dict:
    _case(db, case_id)
    row = create_review(UUID(case_id), ReviewRequest(**request.model_dump()), db)
    _event(db, "CASE", case_id, "ADMIN_REVIEW", request.reviewer_id, {"review_id": row.record_id, "decision": row.status})
    return {"record_id": row.record_id, "case_id": row.case_id, "status": row.status, "payload": row.payload}


@router.get("/submissions")
def admin_submissions(db: Session = Depends(get_db)) -> dict:
    from backend.app.submission.api import _submission_payload
    items = db.query(Submission).order_by(Submission.created_at.desc()).all()
    result = []
    for item in items:
        record = _submission_payload(db, item)
        case = db.query(Case).filter(Case.case_id == item.case_id).first()
        record.update({"submission_mode": item.submission_mode,
                       "submitted_at": item.created_at,
                       "acknowledgement_status": "ACKNOWLEDGED" if item.status == "ACKNOWLEDGED" else "PENDING" if item.status == "SUBMITTED" else None,
                       "retry_attempts": db.query(SubmissionAttempt).filter(SubmissionAttempt.original_submission_id == item.submission_id).count()})
        result.append(record)
    return {"items": result, "total": len(result)}


@router.delete("/session/submissions")
def clear_admin_session_submissions(
    request: AdminSessionSubmissionCleanupRequest,
    db: Session = Depends(get_db),
) -> dict:
    """Remove only submission rows explicitly tracked as new in this Admin session."""
    submission_ids = list(dict.fromkeys(request.submission_ids))
    if not submission_ids:
        return {"deleted": 0, "submission_ids": []}

    rows = db.query(Submission).filter(Submission.submission_id.in_(submission_ids)).all()
    matched_ids = [row.submission_id for row in rows]
    if not matched_ids:
        return {"deleted": 0, "submission_ids": []}

    db.query(Acknowledgement).filter(Acknowledgement.submission_id.in_(matched_ids)).delete(synchronize_session=False)
    db.query(SubmissionAttempt).filter(
        or_(
            SubmissionAttempt.original_submission_id.in_(matched_ids),
            SubmissionAttempt.new_submission_id.in_(matched_ids),
        )
    ).delete(synchronize_session=False)
    for row in rows:
        db.delete(row)
    db.commit()
    return {"deleted": len(matched_ids), "submission_ids": matched_ids}


@router.get("/submissions/{submission_id}")
def admin_submission(submission_id: str, db: Session = Depends(get_db)) -> dict:
    simulated_record = db.query(CaseWorkflowRecord).filter(
        CaseWorkflowRecord.record_id == submission_id,
        CaseWorkflowRecord.record_type == "ADMIN_DEMO_SUBMISSION",
    ).first()
    if simulated_record is not None:
        case = db.query(Case).filter(Case.case_id == simulated_record.case_id).first()
        if case is None:
            raise HTTPException(status_code=404, detail="Case not found for simulated workflow record.")
        return {
            "submission_id": simulated_record.record_id,
            "case_id": simulated_record.case_id,
            "status": "SIMULATED",
            "destination": "DEMO_SIMULATION",
            "channel": "DEMO_SIMULATION",
            "submission_mode": case.submission_mode,
            "created_at": simulated_record.created_at,
            "patient": case.patient or {},
            "disease": case.disease,
            "jurisdiction": case.jurisdiction,
            "warnings": ["Local simulated result; no external transmission was made."],
            "errors": [],
            "acknowledgement": None,
        }

    from backend.app.submission.api import _get_submission, _submission_payload
    row = _get_submission(db, submission_id)
    data = _submission_payload(db, row)
    case = db.query(Case).filter(Case.case_id == row.case_id).first()
    data["submission_mode"] = row.submission_mode
    data["attempts"] = [{"attempt_id": a.attempt_id, "number": a.attempt_number, "status": a.status, "new_submission_id": a.new_submission_id, "reason": a.reason, "created_at": a.created_at} for a in db.query(SubmissionAttempt).filter(SubmissionAttempt.original_submission_id == submission_id).order_by(SubmissionAttempt.attempt_number).all()]
    ack = db.query(Acknowledgement).filter(Acknowledgement.submission_id == submission_id).order_by(Acknowledgement.received_at.desc()).first()
    data["acknowledgement"] = {"acknowledgement_id": ack.acknowledgement_id, "status": ack.status, "received_at": ack.received_at, "errors": ack.errors} if ack else None
    return data


@router.post("/submissions/{submission_id}/acknowledge")
def admin_acknowledge(submission_id: str, db: Session = Depends(get_db)) -> dict:
    try:
        result = AcknowledgementService().process_acknowledgement(AcknowledgementRequest(submission_id=submission_id), db)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if result.status == "ACKNOWLEDGED":
        _event(db, "SUBMISSION", submission_id, "ADMIN_ACKNOWLEDGED", "admin", {"status": result.status, "acknowledgement_id": result.acknowledgement_id})
    else:
        raise HTTPException(status_code=409, detail={"message": "Acknowledgement was not eligible.", "result": result.model_dump(mode="json")})
    return result.model_dump(mode="json")


@router.post("/submissions/{submission_id}/retry")
def admin_retry(submission_id: str, reason: str | None = None, db: Session = Depends(get_db)) -> dict:
    try:
        result = RetryResubmissionService().retry(RetryResubmissionRequest(submission_id=submission_id, reason=reason), db)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    _event(db, "SUBMISSION", submission_id, "ADMIN_RETRY", "admin", result.model_dump(mode="json"))
    if result.status in {"NOT_ELIGIBLE", "BLOCKED"}:
        raise HTTPException(status_code=409, detail=result.model_dump(mode="json"))
    return result.model_dump(mode="json")


@router.post("/cases/{case_id}/dispatch")
def admin_dispatch(case_id: str, actor_id: str = "admin", db: Session = Depends(get_db)) -> dict:
    try:
        parsed_case_id = UUID(case_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="case_id must be a UUID.") from exc
    case = db.query(Case).filter(Case.case_id == parsed_case_id).with_for_update().first()
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found.")

    queue = _latest(db, str(case.case_id), "ADMIN_QUEUE")
    if queue and queue.status == "DISPATCHED":
        submission_id = (queue.payload or {}).get("submission_id")
        submission = db.query(Submission).filter(Submission.submission_id == submission_id).first() if submission_id else None
        if submission is not None:
            return {
                "case_id": str(case.case_id),
                "submission_mode": submission.submission_mode,
                "report_id": submission.report_id,
                "ecr_id": submission.ecr_id,
                "submission_id": submission.submission_id,
                "status": submission.status,
                "destination": submission.destination,
                "errors": submission.errors or [],
                "warnings": submission.warnings or [],
            }
        raise HTTPException(status_code=409, detail="This case has already been dispatched.")

    _eligible_for_dispatch(db, case)
    if case.submission_mode == "BATCH":
        raise HTTPException(status_code=409, detail="BATCH cases must be dispatched through a batch.")
    try:
        result = ECRSubmissionService().submit(ECRSubmissionRequest(case_id=case_id), db)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    row = CaseWorkflowRecord(case_id=case_id, record_type="ADMIN_QUEUE", status="DISPATCHED" if result.status == "SUBMITTED" else "FAILED", actor_id=actor_id, payload={"submission_id": result.submission_id, "status": result.status})
    db.add(row); db.commit()
    _event(db, "CASE", case_id, "ADMIN_DISPATCH", actor_id, result.model_dump(mode="json"))
    return result.model_dump(mode="json")


def _batch_payload(row: CaseWorkflowRecord) -> dict:
    payload = dict(row.payload or {})
    display_batch_id = payload.pop("batch_id", None)
    return {
        **payload,
        "batch_id": row.record_id,
        "display_batch_id": display_batch_id,
        "status": row.status,
        "created_at": row.created_at,
    }


@router.get("/batches")
def list_batches(db: Session = Depends(get_db)) -> dict:
    rows = db.query(CaseWorkflowRecord).filter(CaseWorkflowRecord.record_type == "ADMIN_BATCH").order_by(CaseWorkflowRecord.created_at.desc()).all()
    return {"items": [_batch_payload(row) for row in rows], "total": len(rows)}


@router.post("/batches", status_code=201)
def create_batch(request: BatchCreateRequest, db: Session = Depends(get_db)) -> dict:
    if len(set(request.case_ids)) != len(request.case_ids):
        raise HTTPException(status_code=422, detail="case_ids must be unique.")
    cases = [_case(db, case_id) for case_id in request.case_ids]
    jurisdictions = {case.jurisdiction for case in cases}
    if len(jurisdictions) != 1:
        raise HTTPException(status_code=409, detail="All batch cases must share a jurisdiction.")
    for case in cases:
        if case.submission_mode != "BATCH":
            raise HTTPException(status_code=409, detail=f"Case {case.case_id} is not in BATCH mode.")
        _eligible_for_dispatch(db, case)
    row = CaseWorkflowRecord(case_id=str(cases[0].case_id), record_type="ADMIN_BATCH", status="PENDING", actor_id=request.actor_id, payload={"case_ids": request.case_ids, "jurisdiction": next(iter(jurisdictions)), "submission_ids": []})
    db.add(row); db.commit(); db.refresh(row)
    _event(db, "BATCH", row.record_id, "ADMIN_BATCH_CREATED", request.actor_id, row.payload)
    return _batch_payload(row)


@router.get("/batches/{batch_id}")
def get_batch(batch_id: str, db: Session = Depends(get_db)) -> dict:
    row = db.query(CaseWorkflowRecord).filter(CaseWorkflowRecord.record_id == batch_id, CaseWorkflowRecord.record_type == "ADMIN_BATCH").first()
    if row is None: raise HTTPException(status_code=404, detail="Batch not found.")
    return _batch_payload(row)


@router.post("/batches/{batch_id}/dispatch")
def dispatch_batch(batch_id: str, actor_id: str = "admin", db: Session = Depends(get_db)) -> dict:
    row = db.query(CaseWorkflowRecord).filter(CaseWorkflowRecord.record_id == batch_id, CaseWorkflowRecord.record_type == "ADMIN_BATCH").first()
    if row is None: raise HTTPException(status_code=404, detail="Batch not found.")
    if row.status != "PENDING": raise HTTPException(status_code=409, detail="Batch is not pending dispatch.")
    case_ids = (row.payload or {}).get("case_ids")
    if not isinstance(case_ids, list) or not case_ids:
        raise HTTPException(status_code=409, detail="Batch has no linked cases and cannot be dispatched.")
    outcomes = []
    for case_id in case_ids:
        case = _case(db, case_id); _eligible_for_dispatch(db, case)
        try:
            outcome = ECRSubmissionService().submit(ECRSubmissionRequest(case_id=case_id), db).model_dump(mode="json")
        except ValueError as exc:
            outcome = {"case_id": case_id, "status": "FAILED", "errors": [str(exc)]}
        outcomes.append(outcome)
        db.add(CaseWorkflowRecord(case_id=case_id, record_type="ADMIN_QUEUE", status="DISPATCHED" if outcome.get("status") == "SUBMITTED" else "FAILED", actor_id=actor_id, payload={"batch_id": batch_id, "submission_id": outcome.get("submission_id"), "status": outcome.get("status")}))
        db.commit()
    row.status = "DISPATCHED" if all(x.get("status") == "SUBMITTED" for x in outcomes) else "PARTIAL_FAILURE"
    row.payload = {**row.payload, "submission_ids": [x.get("submission_id") for x in outcomes if x.get("submission_id")], "results": outcomes}
    db.commit()
    _event(db, "BATCH", batch_id, "ADMIN_BATCH_DISPATCH", actor_id, row.payload)
    return _batch_payload(row)


@router.get("/deadlines")
def admin_deadlines(db: Session = Depends(get_db)) -> dict:
    today = datetime.now(timezone.utc).date(); soon = today + timedelta(days=3)
    result = {"overdue": [], "due_today": [], "due_soon": [], "completed": []}
    for case in db.query(Case).filter(Case.deadline.isnot(None)).order_by(Case.deadline).all():
        patient = case.patient if isinstance(case.patient, dict) else {}
        patient_name = patient.get("full_name") or patient.get("name")
        if isinstance(patient_name, dict):
            patient_name = patient_name.get("text") or " ".join(
                str(part) for part in [patient_name.get("given"), patient_name.get("family")]
                if part
            )
        if not patient_name:
            patient_name = " ".join(
                str(part) for part in [
                    patient.get("first_name") or patient.get("given_name"),
                    patient.get("last_name") or patient.get("family_name"),
                ]
                if part
            ) or None
        item = {
            "case_id": str(case.case_id),
            "deadline": case.deadline,
            "jurisdiction": case.jurisdiction,
            "status": case.status,
            "patient_name": patient_name,
            "condition": case.disease,
            "priority": case.severity,
            "submission_mode": case.submission_mode,
        }
        submitted = db.query(Submission.submission_id).filter(Submission.case_id == str(case.case_id), Submission.status.in_(("SUBMITTED", "ACKNOWLEDGED"))).first()
        if submitted: result["completed"].append(item); continue
        deadline_date = case.deadline.astimezone(timezone.utc).date() if case.deadline.tzinfo else case.deadline.date()
        if deadline_date < today: result["overdue"].append(item)
        elif deadline_date == today: result["due_today"].append(item)
        elif deadline_date <= soon: result["due_soon"].append(item)
    return result


@router.get("/audit")
def admin_audit(db: Session = Depends(get_db)) -> dict:
    rows = (db.query(AuditEvent)
            .filter(or_(AuditEvent.source_agent == "admin_api", AuditEvent.event_type == "ADMIN_QUEUE_QUEUED"))
            .order_by(AuditEvent.event_timestamp.desc()).limit(500).all())
    return {"items": [{"audit_id": x.audit_id, "entity_type": x.entity_type, "entity_id": x.entity_id, "event_type": x.event_type, "actor_id": x.actor_id, "status": x.status, "new_value": x.new_value, "timestamp": x.event_timestamp} for x in rows], "total": len(rows)}
