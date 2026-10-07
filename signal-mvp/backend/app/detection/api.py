from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.agents.document_intelligence.service import process_documents
from backend.app.agents.nlp_evidence.service import extract_evidence
from backend.app.canonical.query_service import (
    CanonicalPatientNotFoundError,
    get_patient_context,
)
from backend.app.database import get_db
from backend.app.candidate.service import persist_detection_candidates
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

    documents = process_documents(
        context.get("clinical_documents", [])
    )

    documents_with_text = [
        document
        for document in documents
        if isinstance(document.get("text"), str)
        and document["text"].strip()
    ]

    document_evidence: list[dict[str, Any]] = []
    document_evidence_error: str | None = None

    if not documents_with_text:
        document_evidence_status = "no_document_text"
    else:
        try:
            document_evidence = extract_evidence(
                documents_with_text
            )
            document_evidence_status = "completed"

        except RuntimeError as exc:
            print(
                f"❌ DOCUMENT EVIDENCE CONFIG ERROR: "
                f"{type(exc).__name__}: {exc}"
            )
            document_evidence_status = "failed"
            document_evidence_error = _document_ai_error_message(exc)

        except Exception as exc:
            print(
                f"❌ DOCUMENT EVIDENCE ERROR: "
                f"{type(exc).__name__}: {exc}"
            )
            document_evidence_status = "failed"
            document_evidence_error = _document_ai_error_message(exc)

    try:
        result = detect_candidates(
            normalized_patient,
            document_evidence=document_evidence,
        )

        result["document_evidence_status"] = document_evidence_status
        result["document_evidence_count"] = len(document_evidence)
        if document_evidence_error:
            result["document_evidence_error"] = document_evidence_error
        result["candidates"] = [
            {
                **candidate,
                "candidate_id": candidate_row.candidate_id,
                "status": candidate_row.status,
            }
            for candidate_row, candidate in zip(
                persist_detection_candidates(db, result),
                result["candidates"],
                strict=True,
            )
        ]

        return result

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc


def _document_ai_error_message(exc: Exception) -> str:
    message = str(exc).casefold()
    busy_markers = (
        "429",
        "529",
        "rate limit",
        "rate_limit",
        "too many requests",
        "overloaded",
        "model is busy",
        "temporarily unavailable",
        "server overloaded",
        "capacity",
        "503",
    )
    if any(marker in message for marker in busy_markers):
        return (
            "The AI model is busy or rate limited, so document analysis did not "
            "finish. Your uploaded document is saved. Try detection again shortly; "
            "structured record detection may still have completed."
        )
    return (
        "AI document analysis failed, so uploaded documents were not included in "
        "this detection run. Your documents are saved. Try again or check the "
        "backend error log. Structured record detection may still have completed."
    )


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
        print(
            f"❌ EVIDENCE EXTRACTION ERROR: "
            f"{type(exc).__name__}: {exc}"
        )

        raise HTTPException(
            status_code=502,
            detail=(
                "Clinical evidence extraction failed: "
                f"{type(exc).__name__}: {exc}"
            ),
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
