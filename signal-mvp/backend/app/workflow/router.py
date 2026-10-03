from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.database import get_db

from .schemas import CaseJourneyResponse
from .service import get_case_journey


router = APIRouter(prefix="/api/workflow", tags=["Workflow"])


@router.get(
    "/cases/{case_id}/journey",
    response_model=CaseJourneyResponse,
)
def read_case_journey(
    case_id: UUID,
    db: Session = Depends(get_db),
) -> CaseJourneyResponse:
    journey = get_case_journey(db, case_id)
    if journey is None:
        raise HTTPException(status_code=404, detail=f"Case not found: {case_id}")
    return journey
