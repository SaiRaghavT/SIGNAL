from datetime import datetime, timezone
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
from backend.app.agents.audit_ledger.schemas import AuditEventCreate
from backend.app.agents.audit_ledger.service import AuditLedgerService
from backend.app.detection.adapter import canonical_context_to_detection_input
from backend.app.detection.candidate_service import detect_candidates


router = APIRouter(
    prefix="/api/detection",
    tags=["Candidate Detection"],
)


class CandidateDetectionRequest(BaseModel):
    patient_id: UUID


class PersistDetectedCandidateRequest(BaseModel):
    patient_id: UUID
    candidate: dict[str, Any]


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

        except Exception as exc:
            print(
                f"❌ DOCUMENT EVIDENCE ERROR: "
                f"{type(exc).__name__}: {exc}"
            )
            document_evidence_status = "failed"

    try:
        result = detect_candidates(
            normalized_patient,
            document_evidence=document_evidence,
        )

        result["document_evidence_status"] = document_evidence_status
        result["document_evidence_count"] = len(document_evidence)
        completed_at = datetime.now(timezone.utc)
        is_demo_patient = (
            (context.get("patient") or {}).get("source_patient_id") == "PAT-HL7-001"
        )
        result["detection_run"] = {
            "status": "PREVIEW" if is_demo_patient else "COMPLETED",
            "completed_at": completed_at.isoformat(),
            "candidate_count": len(result["candidates"]),
        }
        result["demo_mode"] = is_demo_patient
        if is_demo_patient:
            # The John Doe demo run is a session preview. Do not persist its
            # candidates or a completion event just because Run Detection ran.
            result["candidates"] = [
                {**candidate, "status": "PREVIEW"}
                for candidate in result["candidates"]
            ]
        else:
            result["candidates"] = [
                {
                    **candidate,
                    "candidate_id": candidate_row.candidate_id,
                    "case_id": candidate_row.case_id,
                    "status": candidate_row.status,
                }
                for candidate_row, candidate in zip(
                    persist_detection_candidates(db, result),
                    result["candidates"],
                    strict=True,
                )
            ]
            audit_record = AuditLedgerService().record_event(
                AuditEventCreate(
                    entity_type="PATIENT",
                    entity_id=str(request.patient_id),
                    event_type="DETECTION_COMPLETED",
                    actor_type="SYSTEM",
                    actor_id="SIGNAL",
                    source_agent="candidate_detection",
                    status="SUCCESS",
                    description="Patient candidate detection completed.",
                    new_value=result,
                    metadata={"workflow_stage": "DETECTION"},
                    event_timestamp=completed_at,
                ),
                db,
            )
            result["detection_run"]["audit_id"] = audit_record.audit_id

        return result

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc


@router.post("/candidates/persist")
def persist_selected_demo_candidate(
    request: PersistDetectedCandidateRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Persist a demo candidate only after the reviewer selects it."""
    try:
        context = get_patient_context(db=db, patient_id=request.patient_id)
    except CanonicalPatientNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if (context.get("patient") or {}).get("source_patient_id") != "PAT-HL7-001":
        raise HTTPException(status_code=403, detail="This endpoint is only for the SIGNAL demo patient.")

    candidate = dict(request.candidate)
    candidate.pop("candidate_id", None)
    candidate.pop("case_id", None)
    rows = persist_detection_candidates(db, {
        "patient_id": str(request.patient_id),
        "candidates": [candidate],
    })
    if not rows:
        raise HTTPException(status_code=422, detail="Selected result did not contain a persistable candidate.")
    row = rows[0]
    return {
        "candidate_id": row.candidate_id,
        "case_id": row.case_id,
        "status": row.status,
    }


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
