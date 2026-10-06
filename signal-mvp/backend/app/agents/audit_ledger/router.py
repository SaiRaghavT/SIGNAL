from datetime import date, datetime, time, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.audit_event import AuditEvent

from .schemas import AuditEventCreate, AuditEventResponse
from .service import AuditLedgerService


router = APIRouter(
    prefix="/api/agents/audit",
    tags=["Audit Ledger"],
)
api_router = APIRouter(tags=["Audit Ledger"])

service = AuditLedgerService()


@router.post(
    "/events",
    response_model=AuditEventResponse,
    status_code=201,
)
def record_audit_event(
    event: AuditEventCreate,
    db: Session = Depends(get_db),
) -> AuditEventResponse:

    return service.record_event(
        event,
        db,
    )


@router.get("/events", response_model=list[AuditEventResponse])
@api_router.get("/api/audit/events", response_model=list[AuditEventResponse])
def list_audit_events(
    entity_type: str | None = Query(default=None, min_length=1, max_length=100),
    entity_id: str | None = Query(default=None, min_length=1, max_length=255),
    case_id: str | None = Query(default=None, max_length=255),
    patient_id: str | None = Query(default=None, max_length=255),
    submission_id: str | None = Query(default=None, max_length=255),
    event_type: str | None = Query(default=None, max_length=100),
    actor: str | None = Query(default=None, max_length=255),
    workflow_stage: str | None = Query(default=None, max_length=100),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[AuditEventResponse]:
    query = db.query(AuditEvent)
    if entity_type:
        query = query.filter(AuditEvent.entity_type == entity_type)
    if entity_id:
        query = query.filter(AuditEvent.entity_id == entity_id)
    if case_id:
        query = query.filter(AuditEvent.entity_id == case_id)
    if patient_id:
        query = query.filter(AuditEvent.entity_id == patient_id)
    if submission_id:
        query = query.filter(AuditEvent.entity_id == submission_id)
    if event_type:
        query = query.filter(AuditEvent.event_type == event_type)
    if actor:
        query = query.filter(or_(AuditEvent.actor_id == actor, AuditEvent.actor_type == actor))
    if workflow_stage:
        query = query.filter(AuditEvent.metadata_json["workflow_stage"].as_string() == workflow_stage)
    if date_from:
        query = query.filter(AuditEvent.event_timestamp >= datetime.combine(date_from, time.min, tzinfo=timezone.utc))
    if date_to:
        query = query.filter(AuditEvent.event_timestamp < datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=timezone.utc))
    events = query.order_by(AuditEvent.event_timestamp.desc()).limit(500).all()
    return [
        AuditEventResponse(
            audit_id=event.audit_id,
            entity_type=event.entity_type,
            entity_id=event.entity_id,
            event_type=event.event_type,
            actor_type=event.actor_type,
            actor_id=event.actor_id,
            source_agent=event.source_agent,
            status=event.status,
            description=event.description,
            previous_value=event.previous_value,
            new_value=event.new_value,
            metadata=event.metadata_json,
            workflow_stage=event.metadata_json.get("workflow_stage"),
            event_timestamp=event.event_timestamp,
        )
        for event in events
    ]


@api_router.get("/api/audit/events/summary")
def get_audit_event_summary(db: Session = Depends(get_db)) -> dict:
    grouped = db.query(
        AuditEvent.source_agent,
        AuditEvent.status,
        func.count(AuditEvent.audit_id),
    ).group_by(AuditEvent.source_agent, AuditEvent.status).all()
    components: dict[str, dict[str, int]] = {}
    total = success = failure = 0
    for source_agent, status, count in grouped:
        component = source_agent or "unknown"
        status_key = str(status or "UNKNOWN").upper()
        counts = components.setdefault(component, {"total": 0, "success": 0, "failure": 0})
        counts["total"] += count
        total += count
        if status_key == "SUCCESS":
            counts["success"] += count
            success += count
        elif status_key == "FAILURE":
            counts["failure"] += count
            failure += count
    return {"total": total, "success": success, "failure": failure, "by_component": components}


@api_router.get("/api/audit/events/{event_id}", response_model=AuditEventResponse)
def get_audit_event(event_id: str, db: Session = Depends(get_db)) -> AuditEventResponse:
    event = db.query(AuditEvent).filter(AuditEvent.audit_id == event_id).first()
    if event is None:
        raise HTTPException(status_code=404, detail="Audit event not found.")
    return AuditEventResponse(
        audit_id=event.audit_id,
        entity_type=event.entity_type,
        entity_id=event.entity_id,
        event_type=event.event_type,
        actor_type=event.actor_type,
        actor_id=event.actor_id,
        source_agent=event.source_agent,
        status=event.status,
        description=event.description,
        previous_value=event.previous_value,
        new_value=event.new_value,
        metadata=event.metadata_json,
        workflow_stage=event.metadata_json.get("workflow_stage"),
        event_timestamp=event.event_timestamp,
    )
