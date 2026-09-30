from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.database import get_db

from .schemas import (
    ECRSubmissionRequest,
    ECRSubmissionResponse,
)
from .service import ECRSubmissionService


router = APIRouter(
    prefix="/api/agents/ecr-submission",
    tags=["ECR Submission"],
)

service = ECRSubmissionService()


@router.post(
    "/submit",
    response_model=ECRSubmissionResponse,
)
def submit_ecr_endpoint(
    request: ECRSubmissionRequest,
    db: Session = Depends(get_db),
) -> ECRSubmissionResponse:

    try:
        return service.submit(
            request,
            db,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc