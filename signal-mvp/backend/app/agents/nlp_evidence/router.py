from fastapi import APIRouter, HTTPException

from .schemas import NLPEvidenceRequest, NLPEvidenceResponse
from .service import extract_evidence


router = APIRouter(
    prefix="/api/agents/nlp-evidence",
    tags=["NLP Evidence"],
)


@router.post("/extract", response_model=NLPEvidenceResponse)
def extract_evidence_endpoint(
    request: NLPEvidenceRequest,
) -> NLPEvidenceResponse:
    try:
        return NLPEvidenceResponse(
            evidence=extract_evidence(request.documents)
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
