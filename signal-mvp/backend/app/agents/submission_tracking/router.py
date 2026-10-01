from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.database import get_db

from .schemas import (
    SubmissionTrackingRequest,
    SubmissionTrackingResponse,
)
from .service import SubmissionTrackingService


router = APIRouter(
    prefix="/api/agents/submission-tracking",
    tags=["Submission Tracking"],
)

service = SubmissionTrackingService()


@router.post(
    "/track",
    response_model=SubmissionTrackingResponse,
)
def track_submission(
    request: SubmissionTrackingRequest,
    db: Session = Depends(get_db),
) -> SubmissionTrackingResponse:

    try:
        return service.track(
            request,
            db,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc