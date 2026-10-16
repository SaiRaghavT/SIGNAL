from datetime import datetime, timezone
import time
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.ai_detection_logging import get_ai_detection_logger
from backend.app.agents.document_intelligence.service import process_documents
from backend.app.agents.nlp_evidence.service import (
    DocumentAIUnavailableError,
    extract_evidence,
)
from backend.app.canonical.query_service import (
    CanonicalPatientNotFoundError,
    get_patient_context,
)
from backend.app.database import get_db
from backend.app.config.demo import DEMO_PATIENT_SOURCE_ID
from backend.app.config.settings import settings
from backend.app.candidate.service import persist_detection_candidates
from backend.app.agents.audit_ledger.schemas import AuditEventCreate
from backend.app.agents.audit_ledger.service import AuditLedgerService
from backend.app.detection.adapter import canonical_context_to_detection_input
from backend.app.detection.candidate_service import detect_candidates


router = APIRouter(
    prefix="/api/detection",
    tags=["Candidate Detection"],
)
logger = get_ai_detection_logger()


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

    run_id = str(uuid4())
    started = time.monotonic()
    logger.info(
        "Detection started | run_id=%s | patient_id=%s",
        run_id,
        request.patient_id,
    )

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
    logger.info(
        "Patient data loaded | run_id=%s | conditions=%d | lab results=%d | documents=%d",
        run_id,
        len(context.get("conditions", [])),
        len(context.get("lab_results", [])),
        len(context.get("clinical_documents", [])),
    )

    uploaded_document_count = sum(
        1
        for document in context.get("clinical_documents", [])
        if (document.get("provenance") or {}).get("source") == "document_upload"
    )
    try:
        documents = process_documents(context.get("clinical_documents", []))
    except Exception:
        logger.exception(
            "Detection checkpoint run_id=%s stage=document_processing_failed",
            run_id,
        )
        raise

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
        logger.warning(
            "No readable document text found | run_id=%s | uploaded documents=%d | processed documents=%d",
            run_id,
            uploaded_document_count,
            len(documents),
        )
    else:
        logger.info(
            "Document text ready for AI analysis | run_id=%s | documents=%d | total characters=%d",
            run_id,
            len(documents_with_text),
            sum(len(document["text"]) for document in documents_with_text),
        )
        try:
            document_evidence = extract_evidence(
                documents_with_text,
                run_id=run_id,
            )
            document_evidence_status = "completed"
            logger.info(
                "AI document analysis completed | run_id=%s | evidence items=%d",
                run_id,
                len(document_evidence),
            )

        except DocumentAIUnavailableError as exc:
            logger.error(
                "Document processing could not take place | run_id=%s | both AI models are unavailable.",
                run_id,
            )
            document_evidence_status = "failed"
            document_evidence_error = _document_ai_error_message(exc)

        except RuntimeError as exc:
            logger.error(
                "Detection checkpoint run_id=%s stage=document_evidence_failed category=configuration error_type=%s detail=%s",
                run_id,
                type(exc).__name__,
                _document_ai_error_message(exc),
            )
            document_evidence_status = "failed"
            document_evidence_error = _document_ai_error_message(exc)

        except Exception as exc:
            logger.error(
                "Detection checkpoint run_id=%s stage=document_evidence_failed category=provider_or_parse error_type=%s detail=%s",
                run_id,
                type(exc).__name__,
                _document_ai_error_message(exc),
            )
            document_evidence_status = "failed"
            document_evidence_error = _document_ai_error_message(exc)

    try:
        result = detect_candidates(
            normalized_patient,
            document_evidence=document_evidence,
        )
        logger.info(
            "Detection matching completed | run_id=%s | signals=%d | candidates=%d",
            run_id,
            result.get("signal_count", 0),
            result.get("candidate_count", 0),
        )

        result["document_evidence_status"] = document_evidence_status
        result["document_evidence_count"] = len(document_evidence)
        result["uploaded_document_count"] = uploaded_document_count
        if document_evidence_error:
            result["document_evidence_error"] = document_evidence_error
        completed_at = datetime.now(timezone.utc)
        is_demo_patient = (
            (context.get("patient") or {}).get("source_patient_id") == DEMO_PATIENT_SOURCE_ID
        )
        result["detection_run"] = {
            "status": "PREVIEW" if is_demo_patient else "COMPLETED",
            "completed_at": completed_at.isoformat(),
            "candidate_count": len(result["candidates"]),
        }
        result["demo_mode"] = is_demo_patient
        if is_demo_patient:
            # The configured demo run is a session preview. Do not persist its
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

        logger.info(
            "Detection finished | run_id=%s | status=%s | candidates=%d | elapsed=%.2fs",
            run_id,
            result["detection_run"]["status"],
            len(result["candidates"]),
            time.monotonic() - started,
        )
        result["diagnostics"] = {"run_id": run_id}
        return result

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc


def _document_ai_error_message(exc: Exception) -> str:
    if isinstance(exc, DocumentAIUnavailableError):
        return str(exc)

    message = str(exc).casefold()
    if "apiconnectionerror" in type(exc).__name__.casefold() or "connection error" in message:
        return (
            "The backend could not connect to the configured AI provider. This usually points to "
            "backend outbound network, DNS, firewall/proxy, or TLS connectivity. Check that the "
            "backend machine can reach the provider; the uploaded document is still saved. "
            "Search backend/logs/ai_detection.log for the run ID shown below."
        )
    busy_markers = (
        "429", "529", "rate limit", "rate_limit", "too many requests",
        "overloaded", "model is busy", "temporarily unavailable",
        "server overloaded", "capacity", "503",
    )
    if any(marker in message for marker in busy_markers):
        return (
            "The AI model is busy or rate limited, so document analysis did not "
            "finish. Your uploaded document is saved. Try detection again shortly; "
            "structured record detection may still have completed."
        )
    if any(marker in message for marker in ("api key", "api_key", "unauthorized", "permission denied", "403")):
        return (
            "The AI provider rejected the configured credentials or model access. "
            "Check the local provider key and selected model, then restart the backend. "
            "Your uploaded document is saved; structured record detection may still have completed."
        )
    if any(marker in message for marker in ("model not found", "not found", "404", "unsupported model")):
        return (
            "The configured AI model is unavailable to this provider account. "
            "Select a currently available model in the local environment and restart the backend. "
            "Your uploaded document is saved; structured record detection may still have completed."
        )
    detail = " ".join(str(exc).split())
    for secret in (settings.gemini_api_key, settings.groq_api_key):
        if secret:
            detail = detail.replace(secret, "[redacted]")
    detail = detail[:240]
    if detail:
        return (
            f"AI document analysis failed ({type(exc).__name__}: {detail}). "
            "Your uploaded document is saved. Search backend/logs/ai_detection.log for the run ID; "
            "structured record detection may still have completed."
        )
    return (
        "AI document analysis failed, so uploaded documents were not included in "
        "this detection run. Your documents are saved. Try again or check the "
        "backend/logs/ai_detection.log using the run ID shown in the workspace. "
        "Structured record detection may still have completed."
    )


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
    if (context.get("patient") or {}).get("source_patient_id") != DEMO_PATIENT_SOURCE_ID:
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
            f"EVIDENCE EXTRACTION ERROR: "
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
