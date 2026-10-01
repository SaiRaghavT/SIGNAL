from fastapi import APIRouter, HTTPException

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
) -> DeadlineCalculationResponse:

    try:
        return service.calculate(request)

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc