from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.database import get_db

from .schemas import (
    DeadlineEscalationRequest,
    DeadlineEscalationResponse,
)
from .service import DeadlineEscalationService


router = APIRouter(
    prefix="/api/agents/deadline-escalation",
    tags=["Deadline Escalation"],
)

service = DeadlineEscalationService()


@router.post(
    "/evaluate",
    response_model=DeadlineEscalationResponse,
)
def evaluate_deadline(
    request: DeadlineEscalationRequest,
    db: Session = Depends(get_db),
) -> DeadlineEscalationResponse:

    try:
        return service.evaluate(request, db)

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc