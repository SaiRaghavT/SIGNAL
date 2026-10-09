from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.agents.attestation_control.schemas import AttestationRequest
from backend.app.agents.attestation_control.service import AttestationControlService
from backend.app.config.demo import is_demo_case
from backend.app.config.settings import settings
from backend.app.detection.disease_concepts import canonical_disease_id
from backend.app.agents.audit_ledger.schemas import AuditEventCreate
from backend.app.agents.audit_ledger.service import AuditLedgerService
from backend.app.database import get_db
from backend.app.demo.admin_demo_reporting import (
    apply_admin_demo_reporting_defaults,
    canonical_patient_for_case,
)
from backend.app.demo.reset_service import reset_demo
from backend.app.ecr.builder import build_ecr
from backend.app.models.case import Case
from backend.app.models.audit_event import AuditEvent
from backend.app.models.workflow_records import CaseWorkflowRecord, Report
from backend.app.case.report_fields import available_case_report_fields, missing_report_fields
from backend.app.schemas.validation import validate_ecr
from backend.app.submission.gates import smart_fields_for_case
from backend.app.smart_field_population.form_config import TEXAS_MEASLES_FORM
from backend.app.admin.schemas import QueueRequest
from backend.app.agents.deadline_calculation.service import DeadlineCalculationService, NoReportingRuleError

router = APIRouter(tags=["Case Workflow"])

RECORD_TYPES = {"notification": "IMMEDIATE_NOTIFICATION", "investigation": "INVESTIGATION", "validation": "VALIDATION", "review": "REVIEW", "attestation": "ATTESTATION"}
SUBMISSION_READINESS_TYPE = "SUBMISSION_READINESS"
ADMIN_QUEUE_TYPE = "ADMIN_QUEUE"
audit = AuditLedgerService()


def _has_immediate_reporting_rule(case: Case) -> bool:
    """Resolve immediacy from the configured jurisdiction/disease rules."""
    if not case.disease or not case.jurisdiction:
        return False

    from backend.app.rules.resolver import normalize_disease_name

    disease = normalize_disease_name(case.disease)
    if not disease:
        return False

    rules = DeadlineCalculationService()
    rule_ids = [case.rule_id] if case.rule_id else []
    rule_ids.append(None)
    for rule_id in dict.fromkeys(rule_ids):
        try:
            rule = rules._load_rule(disease, case.jurisdiction, rule_id)
        except NoReportingRuleError:
            continue
        timing = str((rule.get("reporting") or {}).get("timing") or "").upper()
        if timing in {"CALL_IMMEDIATELY", "REPORT_IMMEDIATELY", "CALL_FAX_IMMEDIATELY", "IMMEDIATE"}:
            return True
    return False


def _is_synthetic_measles_case(case: Case) -> bool:
    patient = case.patient if isinstance(case.patient, dict) else {}
    facility = case.facility if isinstance(case.facility, dict) else {}
    provenance = patient.get("provenance") if isinstance(patient.get("provenance"), dict) else {}
    source = str(provenance.get("source") or facility.get("source") or "").strip().casefold()
    return (
        source in {"synthea", "signal_demo"}
        and canonical_disease_id(case.disease) == canonical_disease_id("measles")
        and str(case.jurisdiction or "").strip().upper() == "TX"
    )


def _queue_synthetic_demo_case(
    case_id: UUID,
    case: Case,
    request: QueueRequest,
    db: Session,
) -> dict[str, Any]:
    if not settings.demo_queue_enabled:
        raise HTTPException(status_code=403, detail="Synthetic demo queueing is disabled.")
    if not _is_synthetic_measles_case(case):
        raise HTTPException(status_code=403, detail="Demo queueing is limited to synthetic measles cases.")
    if case.jurisdiction_status != "RESOLVED" or not case.jurisdiction:
        raise HTTPException(status_code=409, detail="Resolve the reporting jurisdiction before demo queueing.")
    if not request.demo_review_confirmed:
        raise HTTPException(status_code=409, detail="Confirm the synthetic demo review before queueing.")
    if not _has_immediate_reporting_rule(case):
        raise HTTPException(status_code=409, detail="No configured immediate reporting rule is available for this demo case.")
    if request.submission_mode is not None and request.submission_mode != "IMMEDIATE":
        raise HTTPException(status_code=409, detail="Texas measles demo queue mode must be IMMEDIATE.")

    case.submission_mode = "IMMEDIATE"
    latest = _latest(db, case_id, ADMIN_QUEUE_TYPE)
    if latest and latest.status in {"QUEUED", "READY_FOR_SUBMISSION"}:
        if not (latest.payload or {}).get("demo_submission"):
            raise HTTPException(status_code=409, detail="A non-demo queue record already exists for this case.")
        db.commit()
        return {
            "case_id": str(case_id),
            "queue_status": latest.status,
            "submission_mode": case.submission_mode or "IMMEDIATE",
            "demo_submission": True,
        }

    reviewer_id = request.actor_id.strip()
    demo_payload = {
        "demo_submission": True,
        "notice": "Synthetic demo workflow only; not authorized for external reporting.",
    }

    review = _latest(db, case_id, RECORD_TYPES["review"])
    if review is None or str(review.status or "").upper() not in {"APPROVE", "APPROVED"}:
        _record(
            db,
            case_id,
            RECORD_TYPES["review"],
            "APPROVE",
            {
                **demo_payload,
                "reviewer_id": reviewer_id,
                "reviewer_role": "DEMO_SIMULATION",
                "decision": "APPROVE",
                "comments": "Demo-only review confirmation; this is not a clinical approval.",
                "review_confirmed": True,
            },
            reviewer_id,
        )

    attestation = _latest(db, case_id, RECORD_TYPES["attestation"])
    if attestation is None or str(attestation.status or "").upper() != "ATTESTED":
        _record(
            db,
            case_id,
            RECORD_TYPES["attestation"],
            "ATTESTED",
            {
                **demo_payload,
                "reviewer_id": reviewer_id,
                "reviewer_role": "DEMO_SIMULATION",
                "attestation_status": "ATTESTED",
                "comments": "Demo-only attestation; not authorized for external reporting.",
            },
            reviewer_id,
        )

    row = _record(
        db,
        case_id,
        ADMIN_QUEUE_TYPE,
        "READY_FOR_SUBMISSION",
        {**demo_payload, "submission_mode": case.submission_mode},
        reviewer_id,
    )
    return {
        "case_id": str(case_id),
        "queue_status": row.status,
        "submission_mode": case.submission_mode,
        "demo_submission": True,
        "queued_at": row.created_at,
    }


class NotificationRequest(BaseModel):
    notification_time: datetime
    reporting_user: str = Field(min_length=1, max_length=255)
    notification_method: str = Field(min_length=1, max_length=100)
    status: str = "COMPLETED"
    notes: str | None = None


class InvestigationRequest(BaseModel):
    status: str = Field(min_length=1, max_length=50)
    details: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = None


class ReviewRequest(BaseModel):
    reviewer_id: str = Field(min_length=1, max_length=255)
    reviewer_role: str = Field(min_length=1, max_length=100)
    decision: str
    comments: str | None = None
    review_confirmed: bool = False
    draft_decision: str | None = None
    demo_simulation: bool = False


class AttestationBody(BaseModel):
    reviewer_id: str = Field(min_length=1, max_length=255)
    reviewer_role: str = Field(min_length=1, max_length=100)
    attestation_status: str = "ATTESTED"
    comments: str | None = None
    demo_simulation: bool = False


class SubmissionReadinessRequest(BaseModel):
    actor_id: str = Field(min_length=1, max_length=255)
    review_confirmed: bool = False
    review_decision: str | None = None
    attestation_confirmed: bool = False


class DemoWorkflowResetRequest(BaseModel):
    reset_scope: str = Field(pattern="^REPORTING_WORKFLOW$")


@router.post("/api/cases/{case_id}/queue", status_code=201)
def queue_case(case_id: UUID, request: QueueRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    # Lock the case while checking the latest queue row so concurrent clicks
    # serialize and cannot create duplicate active handoffs.
    case = db.query(Case).filter(Case.case_id == case_id).with_for_update().first()
    if case is None:
        raise HTTPException(status_code=404, detail=f"Case not found: {case_id}")
    if request.demo_submission:
        return _queue_synthetic_demo_case(case_id, case, request, db)

    latest = _latest(db, case_id, ADMIN_QUEUE_TYPE)
    if latest and latest.status in {"QUEUED", "READY_FOR_SUBMISSION"}:
        return {
            "case_id": str(case_id),
            "queue_status": latest.status,
            "submission_mode": case.submission_mode,
            "queued_at": latest.created_at,
        }
    if latest and latest.status == "DISPATCHED":
        return {
            "case_id": str(case_id),
            "queue_status": latest.status,
            "submission_mode": case.submission_mode,
        }

    review = _latest(db, case_id, RECORD_TYPES["review"])
    attestation = _latest(db, case_id, RECORD_TYPES["attestation"])
    review_status = str(getattr(review, "status", "") or "").strip().upper()
    attestation_status = str(getattr(attestation, "status", "") or "").strip().upper()
    if review_status not in {"APPROVE", "APPROVED"}:
        raise HTTPException(status_code=409, detail="An approved review is required before queueing.")
    if attestation_status != "ATTESTED":
        raise HTTPException(status_code=409, detail="A persisted attestation is required before queueing.")
    validation = _validation(case, db)
    if not validation["valid"]:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Complete and validate the reporting package before queueing.",
                "validation": validation,
            },
        )
    report = (
        db.query(Report)
        .filter(Report.case_id == str(case_id), Report.status == "GENERATED")
        .order_by(Report.created_at.desc())
        .first()
    )
    if report is None:
        raise HTTPException(status_code=409, detail="Generate a report from the saved reporting fields before queueing.")

    # The effective reporting rule determines mode; a client cannot override
    # an immediate jurisdiction rule with a browser-selected value.
    if _has_immediate_reporting_rule(case):
        case.submission_mode = "IMMEDIATE"
    elif not case.submission_mode:
        case.submission_mode = "INDIVIDUAL"
    if request.submission_mode is not None and request.submission_mode != case.submission_mode:
        raise HTTPException(status_code=409, detail="Queue submission mode must match the Case reporting rule.")
    row = _record(
        db,
        case_id,
        ADMIN_QUEUE_TYPE,
        "READY_FOR_SUBMISSION",
        {
            "submission_mode": case.submission_mode,
            "report_id": report.report_id,
            "rule_id": case.rule_id,
            "deadline": case.deadline.isoformat() if case.deadline else None,
            "review_record_id": review.record_id,
            "attestation_record_id": attestation.record_id,
        },
        request.actor_id.strip(),
    )
    return {
        "case_id": str(case_id),
        "queue_status": row.status,
        "submission_mode": case.submission_mode,
        "queued_at": row.created_at,
        "report_id": report.report_id,
        "rule_id": case.rule_id,
        "deadline": case.deadline,
    }


class WorkflowRecordResponse(BaseModel):
    record_id: str
    case_id: str
    record_type: str
    status: str
    actor_id: str | None = None
    payload: dict[str, Any]
    created_at: datetime
    updated_at: datetime


def _case(db: Session, case_id: UUID) -> Case:
    case = db.query(Case).filter(Case.case_id == case_id).first()
    if case is None:
        raise HTTPException(status_code=404, detail=f"Case not found: {case_id}")
    return case


def _latest(db: Session, case_id: UUID, record_type: str) -> CaseWorkflowRecord | None:
    return (
        db.query(CaseWorkflowRecord)
        .filter(CaseWorkflowRecord.case_id == str(case_id), CaseWorkflowRecord.record_type == record_type)
        .order_by(CaseWorkflowRecord.created_at.desc())
        .first()
    )


def _record(
    db: Session,
    case_id: UUID,
    record_type: str,
    status: str,
    payload: dict[str, Any],
    actor_id: str | None = None,
) -> CaseWorkflowRecord:
    row = CaseWorkflowRecord(
        case_id=str(case_id),
        record_type=record_type,
        status=status,
        actor_id=actor_id,
        payload=payload,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    audit.record_event(
        AuditEventCreate(
            entity_type="CASE",
            entity_id=str(case_id),
            event_type=f"{record_type}_{status}",
            actor_type="USER" if actor_id else "SYSTEM",
            actor_id=actor_id or "SIGNAL",
            source_agent=record_type.casefold(),
            status="SUCCESS",
            new_value=payload,
            metadata={"workflow_stage": record_type},
        ),
        db,
    )
    return row


def _workflow_record_data(row: CaseWorkflowRecord | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "record_id": row.record_id,
        "case_id": row.case_id,
        "record_type": row.record_type,
        "status": row.status,
        "actor_id": row.actor_id,
        "payload": row.payload or {},
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def _reporting_field_summary(case: Case) -> dict[str, Any]:
    fields = TEXAS_MEASLES_FORM["fields"]
    missing_fields, _ = missing_report_fields(available_case_report_fields(case))
    missing = set(missing_fields)
    groups = {
        "patient_identification": {"total": 0, "validated": 0},
        "clinical_information": {"total": 0, "validated": 0},
        "laboratory_evidence": {"total": 0, "validated": 0},
        "reporting_information": {"total": 0, "validated": 0},
    }
    for item in fields:
        field = item["field"]
        prefix = field.split(".", 1)[0]
        group = (
            "patient_identification" if prefix == "patient"
            else "clinical_information" if prefix in {"clinical", "rash_fever"}
            else "laboratory_evidence" if prefix == "laboratory"
            else "reporting_information"
        )
        groups[group]["total"] += 1
        if field not in missing:
            groups[group]["validated"] += 1
    return {
        "validated": sum(group["validated"] for group in groups.values()),
        "total": len(fields),
        "sections": groups,
    }


def _submission_readiness_response(case: Case, ready: bool, row: CaseWorkflowRecord | None) -> dict[str, Any]:
    return {
        "ready": ready,
        "record": _workflow_record_data(row),
        "reporting_fields": _reporting_field_summary(case),
    }


@router.post("/api/demo/cases/{case_id}/reset-workflow")
def reset_demo_case_workflow(
    case_id: UUID,
    request: DemoWorkflowResetRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    case = _case(db, case_id)
    if not settings.demo_mode:
        raise HTTPException(status_code=403, detail="Demo workflow reset is disabled. Set DEMO_MODE=true in a development environment.")
    if not is_demo_case(case):
        return {"case_id": str(case_id), "demo_case": False, "reset": False, "reset_scope": request.reset_scope}
    result = reset_demo(db, requested_case_id=case_id)
    return {**result, "demo_case": True, "reset_scope": request.reset_scope}


@router.post("/api/demo/reset")
def reset_signal_demo(db: Session = Depends(get_db)) -> dict[str, Any]:
    # DEMO ONLY: never enable this workflow reset in production.
    if not settings.demo_mode:
        raise HTTPException(status_code=403, detail="Demo workflow reset is disabled. Set DEMO_MODE=true in a development environment.")
    return reset_demo(db)


@router.post("/api/workflow/cases/{case_id}/immediate-notification", response_model=WorkflowRecordResponse, status_code=201)
def create_immediate_notification(case_id: UUID, request: NotificationRequest, db: Session = Depends(get_db)) -> CaseWorkflowRecord:
    case = _case(db, case_id)
    if "measles" not in (case.disease or "").casefold():
        raise HTTPException(status_code=422, detail="Immediate notification is only configured for measles cases.")
    return _record(db, case_id, RECORD_TYPES["notification"], request.status.upper(), request.model_dump(mode="json"), request.reporting_user)


@router.get("/api/workflow/cases/{case_id}/immediate-notification", response_model=WorkflowRecordResponse | None)
def read_immediate_notification(case_id: UUID, db: Session = Depends(get_db)) -> CaseWorkflowRecord | None:
    _case(db, case_id)
    return _latest(db, case_id, RECORD_TYPES["notification"])


@router.get("/api/cases/{case_id}/investigation", response_model=WorkflowRecordResponse | None)
def read_investigation(case_id: UUID, db: Session = Depends(get_db)) -> CaseWorkflowRecord | None:
    _case(db, case_id)
    return _latest(db, case_id, RECORD_TYPES["investigation"])


@router.post("/api/cases/{case_id}/investigation", response_model=WorkflowRecordResponse, status_code=201)
def create_investigation(case_id: UUID, request: InvestigationRequest, db: Session = Depends(get_db)) -> CaseWorkflowRecord:
    _case(db, case_id)
    return _record(db, case_id, RECORD_TYPES["investigation"], request.status.upper(), request.model_dump(mode="json"))


@router.patch("/api/cases/{case_id}/investigation", response_model=WorkflowRecordResponse)
def update_investigation(case_id: UUID, request: InvestigationRequest, db: Session = Depends(get_db)) -> CaseWorkflowRecord:
    _case(db, case_id)
    if _latest(db, case_id, RECORD_TYPES["investigation"]) is None:
        raise HTTPException(status_code=404, detail="Investigation not found.")
    return _record(db, case_id, RECORD_TYPES["investigation"], request.status.upper(), request.model_dump(mode="json"))


def _validation(case: Case, db: Session | None = None) -> dict[str, Any]:
    canonical_patient = canonical_patient_for_case(db, case)
    apply_admin_demo_reporting_defaults(case, canonical_patient)
    ecr = build_ecr(case)
    ecr.status = "REPORT"
    result = validate_ecr(ecr, smart_fields_for_case(case))
    missing_fields = list(result.completion_required)
    return {
        "valid": result.valid,
        "errors": result.errors,
        "warnings": result.warnings,
        "missing_fields": missing_fields,
        "ready_for_review": result.valid,
    }


@router.post("/api/cases/{case_id}/validate")
def validate_case(case_id: UUID, db: Session = Depends(get_db)) -> dict[str, Any]:
    case = _case(db, case_id)
    data = _validation(case, db)
    row = _record(db, case_id, RECORD_TYPES["validation"], "VALID" if data["valid"] else "INVALID", data)
    return {**data, "case_id": str(case_id), "record_id": row.record_id, "status": row.status}


@router.get("/api/cases/{case_id}/validation")
def get_validation(case_id: UUID, db: Session = Depends(get_db)) -> dict[str, Any]:
    case = _case(db, case_id)
    row = _latest(db, case_id, RECORD_TYPES["validation"])
    return {**row.payload, "case_id": str(case_id), "record_id": row.record_id, "status": row.status} if row else _validation(case, db)


@router.get("/api/cases/{case_id}/review", response_model=WorkflowRecordResponse | None)
def get_review(case_id: UUID, db: Session = Depends(get_db)) -> CaseWorkflowRecord | None:
    _case(db, case_id)
    return _latest(db, case_id, RECORD_TYPES["review"])


@router.post("/api/cases/{case_id}/review", response_model=WorkflowRecordResponse, status_code=201)
def create_review(case_id: UUID, request: ReviewRequest, db: Session = Depends(get_db)) -> CaseWorkflowRecord:
    case = _case(db, case_id)
    decision = request.decision.upper()
    if decision not in {"DRAFT", "APPROVE", "REQUEST_INFORMATION", "REJECT"}:
        raise HTTPException(status_code=422, detail="Unsupported review decision.")
    latest_review = _latest(db, case_id, RECORD_TYPES["review"])
    if (
        decision == "APPROVE"
        and latest_review is not None
        and str(latest_review.status or "").upper() in {"APPROVE", "APPROVED"}
        and latest_review.actor_id == request.reviewer_id
    ):
        return latest_review
    # An outstanding autosaved draft must never arrive after an explicit
    # approval and replace the status that gates queueing and dispatch.
    if decision == "DRAFT" and latest_review is not None and latest_review.status == "APPROVE":
        return latest_review
    if request.demo_simulation:
        if not settings.demo_queue_enabled or not _is_synthetic_measles_case(case):
            raise HTTPException(status_code=403, detail="Demo review is limited to enabled synthetic measles cases.")
        if decision != "APPROVE":
            raise HTTPException(status_code=422, detail="Demo review simulation only supports an explicit approval.")
        if not request.review_confirmed:
            raise HTTPException(status_code=409, detail="Confirm the reporting values before demo review approval.")
        payload = request.model_dump(mode="json")
        payload.update({
            "demo_submission": True,
            "notice": "Synthetic demo review only; this is not a clinical approval.",
        })
        return _record(db, case_id, RECORD_TYPES["review"], "APPROVE", payload, request.reviewer_id)
    validation = _validation(case, db)
    if decision == "APPROVE" and not validation["valid"]:
        raise HTTPException(status_code=409, detail={"message": "Case is not valid for approval.", "validation": validation})
    if decision == "APPROVE":
        prior_attestations = db.query(CaseWorkflowRecord).filter(
            CaseWorkflowRecord.case_id == str(case_id),
            CaseWorkflowRecord.record_type == RECORD_TYPES["attestation"],
            CaseWorkflowRecord.status == "ATTESTED",
        ).all()
        for row in prior_attestations:
            row.status = "SUPERSEDED"
        case.status = "REPORT"
        db.commit()
    return _record(db, case_id, RECORD_TYPES["review"], decision, request.model_dump(mode="json"), request.reviewer_id)


@router.patch("/api/cases/{case_id}/review", response_model=WorkflowRecordResponse)
def update_review(case_id: UUID, request: ReviewRequest, db: Session = Depends(get_db)) -> CaseWorkflowRecord:
    _case(db, case_id)
    if _latest(db, case_id, RECORD_TYPES["review"]) is None:
        raise HTTPException(status_code=404, detail="Review not found.")
    return create_review(case_id, request, db)


@router.get("/api/cases/{case_id}/attestation", response_model=WorkflowRecordResponse | None)
def get_attestation(case_id: UUID, db: Session = Depends(get_db)) -> CaseWorkflowRecord | None:
    _case(db, case_id)
    return _latest(db, case_id, RECORD_TYPES["attestation"])


@router.post("/api/cases/{case_id}/attestation", response_model=WorkflowRecordResponse)
def create_attestation(case_id: UUID, request: AttestationBody, db: Session = Depends(get_db)) -> CaseWorkflowRecord:
    case = _case(db, case_id)
    review = _latest(db, case_id, RECORD_TYPES["review"])
    if review is None or str(review.status or "").strip().upper() not in {"APPROVE", "APPROVED"}:
        raise HTTPException(status_code=409, detail="An approved review is required before attestation.")
    latest_attestation = _latest(db, case_id, RECORD_TYPES["attestation"])
    if (
        latest_attestation is not None
        and str(latest_attestation.status or "").upper() == "ATTESTED"
        and latest_attestation.actor_id == request.reviewer_id
    ):
        return latest_attestation
    if request.demo_simulation:
        if not settings.demo_queue_enabled or not _is_synthetic_measles_case(case):
            raise HTTPException(status_code=403, detail="Demo attestation is limited to enabled synthetic measles cases.")
        if not (review.payload or {}).get("demo_submission"):
            raise HTTPException(status_code=409, detail="A demo review confirmation is required before demo attestation.")
        if request.attestation_status.strip().upper() != "ATTESTED":
            raise HTTPException(status_code=422, detail="Demo attestation status must be ATTESTED.")
        payload = request.model_dump(mode="json")
        payload.update({
            "demo_submission": True,
            "notice": "Synthetic demo attestation only; this is not authorization for external reporting.",
        })
        return _record(db, case_id, RECORD_TYPES["attestation"], "ATTESTED", payload, request.reviewer_id)
    if not _validation(case, db)["valid"]:
        raise HTTPException(status_code=409, detail="A valid case is required before attestation.")
    result = AttestationControlService().validate(
        AttestationRequest(
            case_reference=str(case_id),
            reviewer_id=request.reviewer_id,
            reviewer_role=request.reviewer_role,
            attestation_status=request.attestation_status,
            comments=request.comments,
        ),
        db,
    )
    if not result.authorized:
        raise HTTPException(status_code=403, detail=result.message)
    return _record(db, case_id, RECORD_TYPES["attestation"], "ATTESTED", result.model_dump(mode="json"), request.reviewer_id)


@router.get("/api/cases/{case_id}/submission-readiness")
def get_submission_readiness(case_id: UUID, db: Session = Depends(get_db)) -> dict[str, Any]:
    case = _case(db, case_id)
    queue_record = _latest(db, case_id, ADMIN_QUEUE_TYPE)
    if queue_record is not None and queue_record.status in {"QUEUED", "READY_FOR_SUBMISSION"}:
        return _submission_readiness_response(case, True, queue_record)

    row = _latest(db, case_id, SUBMISSION_READINESS_TYPE)
    valid = _validation(case, db)["valid"]
    current = (
        row is not None
        and row.status == "READY"
        and valid
    )
    return _submission_readiness_response(case, current, row)


@router.post("/api/cases/{case_id}/submission-readiness")
def mark_submission_ready(
    case_id: UUID,
    request: SubmissionReadinessRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    case = _case(db, case_id)
    validation = _validation(case, db)
    review = _latest(db, case_id, RECORD_TYPES["review"])
    attestation = _latest(db, case_id, RECORD_TYPES["attestation"])
    persisted_review_approved = (
        review is not None
        and (review.status or "").strip().upper() in {"APPROVE", "APPROVED"}
    )
    if not persisted_review_approved:
        raise HTTPException(status_code=409, detail="An approved human review is required before queue readiness.")
    if attestation is None or attestation.status != "ATTESTED":
        raise HTTPException(status_code=409, detail="An attestation confirmation is required before queue readiness.")
    if not validation["valid"]:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Complete and validate the required reporting fields before queue readiness.",
                "validation": validation,
            },
        )
    existing = _latest(db, case_id, SUBMISSION_READINESS_TYPE)
    queue_status = "READY"
    if existing is not None and existing.status == queue_status:
        return _submission_readiness_response(case, True, existing)
    row = _record(
        db,
        case_id,
        SUBMISSION_READINESS_TYPE,
        queue_status,
        {
            "ready_for_authorized_reporting": True,
            "queued_for_completion": False,
            "missing_fields": validation["missing_fields"],
        },
        request.actor_id.strip(),
    )
    return _submission_readiness_response(case, True, row)


@router.get("/api/cases/{case_id}/reportability")
def case_reportability(case_id: UUID, db: Session = Depends(get_db)) -> dict[str, Any]:
    case = _case(db, case_id)
    return {
        "case_id": str(case.case_id),
        "decision": case.reportability_decision,
        "disease": case.disease,
        "jurisdiction": case.jurisdiction,
        "rule": case.rule_id,
        "evidence": {
            "clinical": case.clinical_evidence,
            "laboratory": case.laboratory_evidence,
            "ai": case.ai_evidence,
        },
        "warnings": case.warnings or [],
        "reason": case.final_decision,
    }


@router.get("/api/cases/{case_id}/deadline")
def case_deadline(case_id: UUID, db: Session = Depends(get_db)) -> dict[str, Any]:
    case = _case(db, case_id)
    if case.deadline is None:
        raise HTTPException(status_code=404, detail="No deadline has been calculated for this case.")
    return {"case_id": str(case.case_id), "deadline": case.deadline, "severity": case.severity}


@router.get("/api/workflow/cases/{case_id}/timeline")
def case_timeline(case_id: UUID, db: Session = Depends(get_db)) -> dict[str, Any]:
    _case(db, case_id)
    rows = (
        db.query(CaseWorkflowRecord)
        .filter(CaseWorkflowRecord.case_id == str(case_id))
        .order_by(CaseWorkflowRecord.created_at.asc())
        .all()
    )
    audit_events = (
        db.query(AuditEvent)
        .filter(AuditEvent.entity_type == "CASE", AuditEvent.entity_id == str(case_id))
        .order_by(AuditEvent.event_timestamp.asc())
        .all()
    )
    events = [
        {
            "event_id": item.record_id,
            "event_type": item.record_type,
            "status": item.status,
            "actor_id": item.actor_id,
            "timestamp": item.created_at,
            "data": item.payload,
        }
        for item in rows
    ] + [
        {
            "event_id": item.audit_id,
            "event_type": item.event_type,
            "status": item.status,
            "actor_id": item.actor_id,
            "timestamp": item.event_timestamp,
            "data": item.new_value or {},
            "workflow_stage": (item.metadata_json or {}).get("workflow_stage"),
        }
        for item in audit_events
    ]
    events.sort(key=lambda item: item["timestamp"])
    return {
        "case_id": str(case_id),
        "events": events,
    }
