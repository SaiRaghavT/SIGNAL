from uuid import uuid4

from sqlalchemy.orm import Session

from backend.app.models.audit_event import AuditEvent

from .schemas import (
    AuditEventCreate,
    AuditEventResponse,
)


class AuditLedgerService:

    def record_event(
        self,
        event: AuditEventCreate,
        db: Session,
    ) -> AuditEventResponse:

        audit_id = str(uuid4())

        audit_event = AuditEvent(
            audit_id=audit_id,
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
            metadata_json=event.metadata,
            event_timestamp=event.event_timestamp,
        )

        db.add(audit_event)
        db.commit()
        db.refresh(audit_event)

        return AuditEventResponse(
            audit_id=audit_event.audit_id,
            entity_type=audit_event.entity_type,
            entity_id=audit_event.entity_id,
            event_type=audit_event.event_type,
            actor_type=audit_event.actor_type,
            actor_id=audit_event.actor_id,
            source_agent=audit_event.source_agent,
            status=audit_event.status,
            description=audit_event.description,
            previous_value=audit_event.previous_value,
            new_value=audit_event.new_value,
            metadata=audit_event.metadata_json,
            event_timestamp=audit_event.event_timestamp,
        )
