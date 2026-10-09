from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.database import get_db

from .schemas import (
    PublicHealthFollowupRequest,
    PublicHealthFollowupResponse,
)
from .service import PublicHealthFollowupService


router = APIRouter(
    prefix="/api/agents/public-health-followup",
    tags=["Public Health Follow-up"],
)

service = PublicHealthFollowupService()


@router.post(
    "/process",
    response_model=PublicHealthFollowupResponse,
)
def process_followup(
    request: PublicHealthFollowupRequest,
    db: Session = Depends(get_db),
) -> PublicHealthFollowupResponse:

    try:
        return service.process(
            request,
            db,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc