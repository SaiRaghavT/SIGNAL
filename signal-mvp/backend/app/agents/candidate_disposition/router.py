from fastapi import APIRouter

from .schemas import CandidateDispositionRequest, CandidateDispositionResponse
from .service import determine_candidate_disposition


router = APIRouter(tags=["Candidate Disposition"])


@router.post(
    "/api/candidate/disposition",
    response_model=CandidateDispositionResponse,
)
def determine_candidate_disposition_endpoint(
    request: CandidateDispositionRequest,
) -> CandidateDispositionResponse:
    """Return the candidate outcome and reasons for that disposition."""

    result = determine_candidate_disposition(request)
    return CandidateDispositionResponse(
        candidate_id=result.candidate_id,
        final_decision=result.final_decision,
        reasons=result.reasons,
        warnings=result.warnings,
    )
