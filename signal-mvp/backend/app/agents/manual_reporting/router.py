from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.database import get_db

from .schemas import (
    ManualReportingRequest,
    ManualReportingResponse,
)
from .service import ManualReportingService


router = APIRouter(
    prefix="/api/agents/manual-reporting",
    tags=["Manual Reporting"],
)

service = ManualReportingService()


@router.post(
    "/prepare",
    response_model=ManualReportingResponse,
)
def prepare_manual_report(
    request: ManualReportingRequest,
    db: Session = Depends(get_db),
) -> ManualReportingResponse:

    try:
        return service.prepare_manual_report(
            request,
            db,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc