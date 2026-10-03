from fastapi import APIRouter, HTTPException

from .schemas import (
    DocumentIntelligenceRequest,
    DocumentIntelligenceResponse,
)
from .service import process_documents


router = APIRouter(
    prefix="/api/agents/document-intelligence",
    tags=["Document Intelligence"],
)


@router.post("/process", response_model=DocumentIntelligenceResponse)
def process_documents_endpoint(
    request: DocumentIntelligenceRequest,
) -> DocumentIntelligenceResponse:
    try:
        return DocumentIntelligenceResponse(
            documents=process_documents(request.documents)
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
