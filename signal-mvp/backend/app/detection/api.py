from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.agents.document_intelligence.agent import process_documents
from backend.app.agents.nlp_evidence.agent import extract_evidence
from backend.app.canonical.query_service import (
    CanonicalPatientNotFoundError,
    get_patient_context,
)
from backend.app.database import get_db
from backend.app.detection.adapter import canonical_context_to_detection_input
from backend.app.detection.candidate_service import detect_candidates


router = APIRouter(
    prefix="/api/detection",
    tags=["Candidate Detection"],
)


class CandidateDetectionRequest(BaseModel):
    patient_id: UUID


@router.post("/candidates")
def detect_patient_candidates(
    request: CandidateDetectionRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Detect potential candidates from one patient's canonical data."""

    try:
        context = get_patient_context(
            db=db,
            patient_id=request.patient_id,
        )
    except CanonicalPatientNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    normalized_patient = canonical_context_to_detection_input(context)

    try:
        return detect_candidates(normalized_patient)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc


@router.post("/evidence")
def extract_patient_evidence(
    request: CandidateDetectionRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Extract document evidence for one canonical patient."""

    try:
        context = get_patient_context(
            db=db,
            patient_id=request.patient_id,
        )
    except CanonicalPatientNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    documents = process_documents(
        context.get("clinical_documents", [])
    )

    try:
        evidence = extract_evidence(documents)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail="Clinical evidence extraction failed.",
        ) from exc

    return {
        "patient_id": str(request.patient_id),
        "documents_processed": sum(
            bool(document.get("text"))
            for document in documents
        ),
        "evidence_count": len(evidence),
        "evidence": evidence,
    }
