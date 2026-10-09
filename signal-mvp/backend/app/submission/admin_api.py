from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.agents.audit_ledger.schemas import AuditEventCreate
from backend.app.agents.audit_ledger.service import AuditLedgerService
from backend.app.agents.ecr_submission.schemas import ECRSubmissionRequest
from backend.app.agents.ecr_submission.service import ECRSubmissionService
from backend.app.database import get_db
from backend.app.ecr.builder import build_ecr
from backend.app.models.audit_event import AuditEvent
from backend.app.models.case import Case
from backend.app.models.submissions import Submission
from backend.app.models.workflow_records import CaseWorkflowRecord, Report
from backend.app.agents.retry_resubmission.schemas import RetryResubmissionRequest
from backend.app.agents.retry_resubmission.service import RetryResubmissionService
from backend.app.schemas.validation import validate_ecr
from backend.app.submission.gates import case_has_current_attestation, smart_fields_for_case

router = APIRouter(prefix="/api/admin", tags=["Reporting Administration"])
ecr_service = ECRSubmissionService()


class BatchCreate(BaseModel):
    case_ids: list[str] = Field(min_length=1, max_length=100)
    created_by: str = "reporting-admin"
    channel: str = "eCR"


class BatchSubmit(BaseModel):
    submitted_by: str = "reporting-admin"


def eligibility(db: Session, case: Case) -> dict:
    blockers: list[str] = []
    warnings = list(case.warnings or [])
    if (case.final_decision or "").upper() != "REPORT":
        blockers.append("An upstream reportability decision of REPORT is required.")
    if (case.jurisdiction_status or "").upper() != "RESOLVED" or not case.jurisdiction:
        blockers.append("Jurisdiction must be resolved.")
    review = db.query(CaseWorkflowRecord).filter_by(case_id=str(case.case_id), record_type="REVIEW").order_by(CaseWorkflowRecord.created_at.desc()).first()
    if not review or review.status != "APPROVE":
        blockers.append("An upstream approved human review is required.")
    attestation = db.query(CaseWorkflowRecord).filter_by(case_id=str(case.case_id), record_type="ATTESTATION").order_by(CaseWorkflowRecord.created_at.desc()).first()
    if not attestation or attestation.status != "ATTESTED" or not case_has_current_attestation(db, case):
        blockers.append("A current required attestation is missing.")
    report = db.query(Report).filter_by(case_id=str(case.case_id), status="GENERATED").order_by(Report.created_at.desc()).first()
    if not report:
        blockers.append("A generated reporting form is required.")
    ecr = build_ecr(case)
    validation = validate_ecr(ecr, smart_fields_for_case(case))
    blockers.extend(validation.errors)
    blockers.extend(validation.completion_required)
    latest = db.query(Submission).filter_by(case_id=str(case.case_id)).order_by(Submission.created_at.desc()).first()
    retryable = False
    if latest and (latest.status or "").upper() in {"SUBMITTED", "ACKNOWLEDGED", "ACCEPTED"}:
        blockers.append(f"Already submitted as {latest.submission_id}.")
    elif latest and (latest.status or "").upper() in {"FAILED", "ERROR", "REJECTED"}:
        technical_markers = ("timeout", "connection", "network", "unavailable", "gateway", "authentication", "temporarily")
        retryable = any(marker in str(error).casefold() for error in (latest.errors or []) for marker in technical_markers)
        blockers.append(f"Submission {latest.submission_id} failed; use the retry workflow." if retryable else f"Submission {latest.submission_id} needs data or validation correction before retry.")
    elif latest and (latest.status or "").upper() not in {"FAILED", "ERROR", "REJECTED"}:
        blockers.append(f"Existing submission {latest.submission_id} must be resolved first.")
    warnings.extend(validation.warnings)
    return {"eligible": not blockers, "retryable": retryable, "status": "eligible" if not blockers else "blocked", "blockers": list(dict.fromkeys(blockers)), "warnings": list(dict.fromkeys(warnings)), "review_complete": bool(review and review.status == "APPROVE"), "attestation_complete": bool(attestation and attestation.status == "ATTESTED" and case_has_current_attestation(db, case)), "report_id": report.report_id if report else None, "submission_id": latest.submission_id if latest else None}


def case_payload(db: Session, case: Case) -> dict:
    report_fields = case.report_fields if isinstance(case.report_fields, dict) else {}
    raw_mode = case.submission_mode or report_fields.get("submission_mode") or "INDIVIDUAL"
    normalized_mode = str(raw_mode).strip().replace("-", "_").replace(" ", "_").upper()
    if normalized_mode in {"PER_CASE", "PERCASE"}:
        normalized_mode = "INDIVIDUAL"
    if normalized_mode not in {"IMMEDIATE", "INDIVIDUAL", "BATCH"}:
        normalized_mode = "INDIVIDUAL"
    return {"case_id": str(case.case_id), "candidate_id": case.candidate_id, "patient": case.patient or {}, "disease": case.disease, "jurisdiction": case.jurisdiction, "facility": case.facility or {}, "provider": case.provider or {}, "deadline": case.deadline, "severity": case.severity, "submission_mode": normalized_mode, "status": case.status, "final_decision": case.final_decision, "reportability_decision": case.reportability_decision, "eligibility": eligibility(db, case)}


@router.get("/submission-queue")
def submission_queue(db: Session = Depends(get_db)) -> dict:
    cases = db.query(Case).order_by(Case.deadline.asc().nullslast(), Case.created_at.desc()).all()
    items = [case_payload(db, case) for case in cases]
    return {"items": items, "total": len(items)}


@router.get("/submission-dashboard")
def submission_dashboard(db: Session = Depends(get_db)) -> dict:
    items = submission_queue(db)["items"]
    submissions = db.query(Submission).all()
    today = datetime.now(timezone.utc).date()
    status = lambda s: (s.status or "").upper()
    draft_rows = db.query(CaseWorkflowRecord).filter_by(record_type="SUBMISSION_BATCH_CASE", status="DRAFT").all()
    pending_batch_count = len({(row.payload or {}).get("batch_id") for row in draft_rows})
    return {"ready_for_submission": sum(item["eligibility"]["eligible"] for item in items), "immediate_reports": sum(item["eligibility"]["eligible"] and item["submission_mode"] == "IMMEDIATE" for item in items), "pending_batch": pending_batch_count, "submitted_today": sum(status(s) in {"SUBMITTED", "ACKNOWLEDGED", "ACCEPTED"} and s.created_at.date() == today for s in submissions), "failed": sum(status(s) in {"FAILED", "ERROR", "REJECTED"} for s in submissions), "awaiting_acknowledgement": sum(status(s) == "SUBMITTED" for s in submissions)}


@router.get("/cases/{case_id}/submission-review")
def submission_review(case_id: str, db: Session = Depends(get_db)) -> dict:
    case = db.query(Case).filter(Case.case_id == case_id).first()
    if not case:
        raise HTTPException(404, "Case not found.")
    payload = case_payload(db, case)
    report = db.query(Report).filter_by(case_id=str(case.case_id), status="GENERATED").order_by(Report.created_at.desc()).first()
    payload["report"] = {"report_id": report.report_id, "form_id": report.form_id, "form_version": report.form_version, "created_at": report.created_at} if report else None
    payload["evidence"] = {"clinical": case.clinical_evidence, "laboratory": case.laboratory_evidence, "sources": case.ai_evidence}
    return payload


@router.post("/cases/{case_id}/submit")
def submit_individual(case_id: str, body: BatchSubmit, db: Session = Depends(get_db)) -> dict:
    case = db.query(Case).filter(Case.case_id == case_id).first()
    if not case:
        raise HTTPException(404, "Case not found.")
    result = eligibility(db, case)
    if not result["eligible"]:
        raise HTTPException(409, {"message": "Case is blocked from submission.", "eligibility": result})
    try:
        response = ecr_service.submit(ECRSubmissionRequest(case_id=case_id, submitted_by=body.submitted_by), db)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return response.model_dump() if hasattr(response, "model_dump") else response.dict()


@router.post("/submissions/{submission_id}/retry")
def retry_failed_submission(submission_id: str, body: BatchSubmit, db: Session = Depends(get_db)) -> dict:
    try:
        response = RetryResubmissionService().retry(RetryResubmissionRequest(submission_id=submission_id, reason="Reporting Administrator retry"), db)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    if response.status not in {"RESUBMITTED"}:
        raise HTTPException(409, {"message": "The submission could not be retried.", "status": response.status, "errors": response.errors})
    AuditLedgerService().record_event(AuditEventCreate(entity_type="CASE", entity_id=response.case_id, event_type="SUBMISSION_RETRIED", actor_type="USER", actor_id=body.submitted_by, source_agent="reporting_admin", status=response.status, new_value={"original_submission_id": response.submission_id, "new_submission_id": response.new_submission_id}, workflow_stage="SUBMISSION"), db)
    return response.model_dump() if hasattr(response, "model_dump") else response.dict()


@router.post("/submission-batches")
def create_batch(body: BatchCreate, db: Session = Depends(get_db)) -> dict:
    if len(set(body.case_ids)) != len(body.case_ids):
        raise HTTPException(422, "Duplicate case IDs are not allowed.")
    cases = [db.query(Case).filter(Case.case_id == case_id).first() for case_id in body.case_ids]
    if any(case is None for case in cases):
        raise HTTPException(404, "One or more cases were not found.")
    checks = [{"case_id": str(case.case_id), "patient": case.patient, **eligibility(db, case)} for case in cases]
    jurisdictions = {case.jurisdiction for case in cases}
    if len(jurisdictions) != 1:
        raise HTTPException(409, {"message": "A batch must use one compatible jurisdiction.", "cases": checks})
    blocked = [item for item in checks if not item["eligible"]]
    if blocked:
        raise HTTPException(409, {"message": "Remove blocked cases before creating the batch.", "eligible_count": len(checks) - len(blocked), "blocked_count": len(blocked), "cases": checks})
    batch_id = f"TX-{datetime.now(timezone.utc).year}-{uuid4().hex[:8].upper()}"
    now = datetime.now(timezone.utc).isoformat()
    for case in cases:
        db.add(CaseWorkflowRecord(case_id=str(case.case_id), record_type="SUBMISSION_BATCH_CASE", status="DRAFT", actor_id=body.created_by, payload={"batch_id": batch_id, "channel": body.channel, "jurisdiction": case.jurisdiction, "created_at": now}))
    db.commit()
    AuditLedgerService().record_event(AuditEventCreate(entity_type="SUBMISSION_BATCH", entity_id=batch_id, event_type="BATCH_CREATED", actor_type="USER", actor_id=body.created_by, source_agent="reporting_admin", status="DRAFT", new_value={"case_ids": body.case_ids, "channel": body.channel}, workflow_stage="SUBMISSION"), db)
    return {"batch_id": batch_id, "jurisdiction": next(iter(jurisdictions)), "channel": body.channel, "cases": checks, "case_count": len(cases), "eligible_count": len(cases), "blocked_count": 0, "status": "DRAFT"}


def get_batch_rows(db: Session, batch_id: str) -> list[CaseWorkflowRecord]:
    rows = db.query(CaseWorkflowRecord).filter(CaseWorkflowRecord.record_type == "SUBMISSION_BATCH_CASE").all()
    return [row for row in rows if (row.payload or {}).get("batch_id") == batch_id]


@router.get("/submission-batches")
def list_batches(db: Session = Depends(get_db)) -> dict:
    rows = db.query(CaseWorkflowRecord).filter(CaseWorkflowRecord.record_type == "SUBMISSION_BATCH_CASE").order_by(CaseWorkflowRecord.created_at.desc()).all()
    grouped: dict[str, list] = {}
    for row in rows:
        grouped.setdefault((row.payload or {}).get("batch_id", ""), []).append(row)
    return {"items": [{"batch_id": batch_id, "status": batch_status(records), "created_at": records[0].payload.get("created_at"), "channel": records[0].payload.get("channel"), "jurisdiction": records[0].payload.get("jurisdiction"), "case_count": len(records), "submissions": [r.payload.get("submission_id") for r in records if r.payload.get("submission_id")]} for batch_id, records in grouped.items()]}


def batch_status(rows: list[CaseWorkflowRecord]) -> str:
    statuses = {row.status for row in rows}
    if statuses == {"DRAFT"}:
        return "DRAFT"
    if statuses <= {"SUBMITTED"}:
        return "SUBMITTED"
    if statuses <= {"SUBMITTED", "FAILED", "BLOCKED"} and "SUBMITTED" in statuses:
        return "PARTIAL"
    if "FAILED" in statuses or "BLOCKED" in statuses:
        return "FAILED"
    return next(iter(statuses), "UNKNOWN")


@router.get("/submission-batches/{batch_id}")
def get_batch(batch_id: str, db: Session = Depends(get_db)) -> dict:
    rows = get_batch_rows(db, batch_id)
    if not rows:
        raise HTTPException(404, "Batch not found.")
    cases = []
    for row in rows:
        case = db.query(Case).filter(Case.case_id == row.case_id).first()
        if case:
            cases.append({**case_payload(db, case), "batch_status": row.status, "submission_id": (row.payload or {}).get("submission_id")})
    return {"batch_id": batch_id, "status": batch_status(rows), "channel": rows[0].payload.get("channel"), "jurisdiction": rows[0].payload.get("jurisdiction"), "case_count": len(rows), "cases": cases}


@router.post("/submission-batches/{batch_id}/submit")
def submit_batch(batch_id: str, body: BatchSubmit, db: Session = Depends(get_db)) -> dict:
    rows = get_batch_rows(db, batch_id)
    if not rows:
        raise HTTPException(404, "Batch not found.")
    if rows[0].status != "DRAFT":
        raise HTTPException(409, "Only a draft batch can be submitted.")
    outcomes = []
    for row in rows:
        case = db.query(Case).filter(Case.case_id == row.case_id).first()
        check = eligibility(db, case) if case else {"eligible": False, "blockers": ["Case not found."]}
        if not check["eligible"]:
            row.status = "BLOCKED"
            row.payload = {**row.payload, "blockers": check["blockers"]}
            outcomes.append({"case_id": row.case_id, "status": "BLOCKED", "errors": check["blockers"]})
            continue
        try:
            response = ecr_service.submit(ECRSubmissionRequest(case_id=row.case_id, submitted_by=body.submitted_by, batch_id=batch_id), db)
            row.status = "SUBMITTED" if response.status.upper() in {"SUBMITTED", "ACKNOWLEDGED"} else "FAILED"
            row.payload = {**row.payload, "submission_id": response.submission_id, "submitted_at": datetime.now(timezone.utc).isoformat(), "destination": response.destination, "errors": response.errors}
            outcomes.append({"case_id": row.case_id, "submission_id": response.submission_id, "status": response.status, "errors": response.errors})
        except ValueError as exc:
            row.status = "FAILED"
            row.payload = {**row.payload, "errors": [str(exc)]}
            outcomes.append({"case_id": row.case_id, "status": "FAILED", "errors": [str(exc)]})
    db.commit()
    aggregate = "SUBMITTED" if all(item["status"].upper() in {"SUBMITTED", "ACKNOWLEDGED"} for item in outcomes) else ("PARTIAL" if any(item["status"].upper() in {"SUBMITTED", "ACKNOWLEDGED"} for item in outcomes) else "FAILED")
    AuditLedgerService().record_event(AuditEventCreate(entity_type="SUBMISSION_BATCH", entity_id=batch_id, event_type="BATCH_SUBMITTED", actor_type="USER", actor_id=body.submitted_by, source_agent="reporting_admin", status=aggregate, new_value={"results": outcomes}, workflow_stage="SUBMISSION"), db)
    return {"batch_id": batch_id, "status": aggregate, "submitted_at": datetime.now(timezone.utc).isoformat(), "case_count": len(rows), "submitted_count": sum(item["status"].upper() in {"SUBMITTED", "ACKNOWLEDGED"} for item in outcomes), "failed_count": sum(item["status"].upper() not in {"SUBMITTED", "ACKNOWLEDGED"} for item in outcomes), "cases": outcomes, "simulated": True}
