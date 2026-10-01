from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.database import get_db

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