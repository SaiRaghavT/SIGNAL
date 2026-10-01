from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.database import get_db

from .schemas import (
    RetryResubmissionRequest,
    RetryResubmissionResponse,
)
from .service import RetryResubmissionService


router = APIRouter(
    prefix="/api/agents/retry-resubmission",
    tags=["Retry & Resubmission"],
)

service = RetryResubmissionService()


@router.post(
    "/retry",
    response_model=RetryResubmissionResponse,
)
def retry_submission(
    request: RetryResubmissionRequest,
    db: Session = Depends(get_db),
) -> RetryResubmissionResponse:

    try:
        return service.retry(
            request,
            db,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc