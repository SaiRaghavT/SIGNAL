from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.database import get_db

from .schemas import (
    AcknowledgementRequest,
    AcknowledgementResponse,
)
from .service import AcknowledgementService


router = APIRouter(
    prefix="/api/agents/acknowledgement",
    tags=["Acknowledgement"],
)

service = AcknowledgementService()


@router.post(
    "/process",
    response_model=AcknowledgementResponse,
)
def process_acknowledgement(
    request: AcknowledgementRequest,
    db: Session = Depends(get_db),
) -> AcknowledgementResponse:

    try:
        return service.process_acknowledgement(
            request,
            db,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc