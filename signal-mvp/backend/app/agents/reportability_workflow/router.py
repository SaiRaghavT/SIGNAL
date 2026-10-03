from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.canonical.query_service import CanonicalPatientNotFoundError

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

    try:
        return process_candidate(request, db)
    except CanonicalPatientNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
