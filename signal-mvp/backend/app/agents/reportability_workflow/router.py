from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.database import get_db

from .schemas import CandidateProcessRequest, CandidateProcessResponse
from .service import process_candidate


router = APIRouter(tags=["Reportability Workflow"])


@router.post(
    "/api/candidate/process",
    response_model=CandidateProcessResponse,
)
def process_candidate_endpoint(
    request: CandidateProcessRequest,
    db: Session = Depends(get_db),
) -> CandidateProcessResponse:
    """Run the end-to-end candidate reportability workflow."""

    return process_candidate(request, db)