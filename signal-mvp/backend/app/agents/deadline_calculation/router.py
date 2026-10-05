from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.database import get_db

from .schemas import (
    DeadlineCalculationRequest,
    DeadlineCalculationResponse,
)
from .service import DeadlineCalculationService


router = APIRouter(
    prefix="/api/agents/deadline",
    tags=["Deadline Calculation"],
)

service = DeadlineCalculationService()


@router.post(
    "/calculate",
    response_model=DeadlineCalculationResponse,
)
def calculate_deadline(
    request: DeadlineCalculationRequest,
    db: Session = Depends(get_db),
) -> DeadlineCalculationResponse:

    try:
        return service.calculate(request, db)

    except ValueError as exc:
        status_code = 404 if str(exc).startswith(("Candidate not found:", "Case not found:")) else 422
        raise HTTPException(
            status_code=status_code,
            detail=str(exc),
        ) from exc