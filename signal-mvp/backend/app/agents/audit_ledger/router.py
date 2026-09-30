from fastapi import APIRouter

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
) -> AuditEventResponse:
    return service.record_event(event)
