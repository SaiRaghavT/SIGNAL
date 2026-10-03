from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.audit_event import AuditEvent

from .schemas import AuditEventCreate, AuditEventResponse
from .service import AuditLedgerService


router = APIRouter(
    prefix="/api/agents/audit",
    tags=["Audit Ledger"],
)

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
def list_audit_events(
    entity_type: str = Query(min_length=1, max_length=100),
    entity_id: str = Query(min_length=1, max_length=255),
    db: Session = Depends(get_db),
) -> list[AuditEventResponse]:
    events = (
        db.query(AuditEvent)
        .filter(
            AuditEvent.entity_type == entity_type,
            AuditEvent.entity_id == entity_id,
        )
        .order_by(AuditEvent.event_timestamp.desc())
        .limit(100)
        .all()
    )
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
            event_timestamp=event.event_timestamp,
        )
        for event in events
    ]
