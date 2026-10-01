from uuid import uuid4

from .schemas import AuditEventCreate, AuditEventResponse


class AuditLedgerService:

    def record_event(
        self,
        event: AuditEventCreate,
    ) -> AuditEventResponse:
        """
        Record an audit event.

        Database persistence will be added after the
        event contract and API are verified.
        """

        audit_id = str(uuid4())

        return AuditEventResponse(
            audit_id=audit_id,
            **event.model_dump(),
        )