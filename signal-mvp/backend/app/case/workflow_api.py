from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.agents.attestation_control.schemas import AttestationRequest
from backend.app.agents.attestation_control.service import AttestationControlService
from backend.app.agents.audit_ledger.schemas import AuditEventCreate
from backend.app.agents.audit_ledger.service import AuditLedgerService
from backend.app.database import get_db
from backend.app.ecr.builder import build_ecr
from backend.app.models.case import Case
from backend.app.models.audit_event import AuditEvent
from backend.app.models.workflow_records import CaseWorkflowRecord
from backend.app.schemas.validation import validate_ecr
from backend.app.submission.gates import smart_fields_for_case
from backend.app.smart_field_population.form_config import TEXAS_MEASLES_FORM

router = APIRouter(tags=["Case Workflow"])

RECORD_TYPES = {"notification": "IMMEDIATE_NOTIFICATION", "investigation": "INVESTIGATION", "validation": "VALIDATION", "review": "REVIEW", "attestation": "ATTESTATION"}
audit = AuditLedgerService()


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


class AttestationBody(BaseModel):
    reviewer_id: str = Field(min_length=1, max_length=255)
    reviewer_role: str = Field(min_length=1, max_length=100)
    attestation_status: str = "ATTESTED"
    comments: str | None = None


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


def _validation(case: Case) -> dict[str, Any]:
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
    data = _validation(case)
    row = _record(db, case_id, RECORD_TYPES["validation"], "VALID" if data["valid"] else "INVALID", data)
    return {**data, "case_id": str(case_id), "record_id": row.record_id, "status": row.status}


@router.get("/api/cases/{case_id}/validation")
def get_validation(case_id: UUID, db: Session = Depends(get_db)) -> dict[str, Any]:
    case = _case(db, case_id)
    row = _latest(db, case_id, RECORD_TYPES["validation"])
    return {**row.payload, "case_id": str(case_id), "record_id": row.record_id, "status": row.status} if row else _validation(case)


@router.get("/api/cases/{case_id}/review", response_model=WorkflowRecordResponse | None)
def get_review(case_id: UUID, db: Session = Depends(get_db)) -> CaseWorkflowRecord | None:
    _case(db, case_id)
    return _latest(db, case_id, RECORD_TYPES["review"])


@router.post("/api/cases/{case_id}/review", response_model=WorkflowRecordResponse, status_code=201)
def create_review(case_id: UUID, request: ReviewRequest, db: Session = Depends(get_db)) -> CaseWorkflowRecord:
    case = _case(db, case_id)
    decision = request.decision.upper()
    if decision not in {"APPROVE", "REQUEST_INFORMATION", "REJECT"}:
        raise HTTPException(status_code=422, detail="Unsupported review decision.")
    validation = _validation(case)
    if decision == "APPROVE" and not validation["valid"]:
        raise HTTPException(status_code=409, detail={"message": "Case is not valid for approval.", "validation": validation})
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
    if review is None or review.status != "APPROVE":
        raise HTTPException(status_code=409, detail="An approved review is required before attestation.")
    if not _validation(case)["valid"]:
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
