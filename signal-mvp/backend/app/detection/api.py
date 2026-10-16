from datetime import datetime, timezone
from contextvars import ContextVar
from functools import wraps
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
from backend.app.database import engine, get_db
from backend.app.config.demo import DEMO_PATIENT_SOURCE_ID
from backend.app.config.settings import settings
from backend.app.candidate.service import _without_persisted_scores, persist_detection_candidates
from backend.app.agents.audit_ledger.schemas import AuditEventCreate
from backend.app.agents.audit_ledger.service import AuditLedgerService
from backend.app.detection.adapter import canonical_context_to_detection_input
from backend.app.detection.candidate_service import detect_candidates
from backend.app.detection.run_lock import try_acquire_patient_detection_lease


router = APIRouter(
    prefix="/api/detection",
    tags=["Candidate Detection"],
)
logger = get_ai_detection_logger()
_DETECTION_RUN_ID: ContextVar[str | None] = ContextVar("detection_run_id", default=None)


def _patient_detection_guard(endpoint):
    """Reject overlapping runs for one patient across all PostgreSQL workers."""
    @wraps(endpoint)
    def guarded(request, db=Depends(get_db)):
        run_id = str(uuid4())
        started = time.perf_counter()
        token = _DETECTION_RUN_ID.set(run_id)
        lease = None
        try:
            try:
                lease = try_acquire_patient_detection_lease(engine, request.patient_id)
            except Exception as exc:
                logger.error(
                    "Detection timing run_id=%s stage=patient_lock_failed elapsed_ms=%.0f error_type=%s",
                    run_id, (time.perf_counter() - started) * 1000, type(exc).__name__,
                )
                raise HTTPException(status_code=503, detail="Detection coordination is temporarily unavailable.") from exc
            if lease is None:
                logger.warning(
                    "Detection timing run_id=%s stage=patient_lock_conflict elapsed_ms=%.0f",
                    run_id, (time.perf_counter() - started) * 1000,
                )
                raise HTTPException(status_code=409, detail="Detection is already running for this patient.")
            return endpoint(request, db)
        finally:
            if lease is not None:
                try:
                    lease.release()
                except Exception as exc:
                    logger.error(
                        "Detection timing run_id=%s stage=patient_lock_release_failed error_type=%s",
                        run_id, type(exc).__name__,
                    )
            logger.info(
                "Detection timing run_id=%s stage=endpoint_complete elapsed_ms=%.0f",
                run_id, (time.perf_counter() - started) * 1000,
            )
            _DETECTION_RUN_ID.reset(token)
    return guarded


class CandidateDetectionRequest(BaseModel):
    patient_id: UUID


class PersistDetectedCandidateRequest(BaseModel):
    patient_id: UUID
    candidate: dict[str, Any]


@router.post("/candidates")
@_patient_detection_guard
def detect_patient_candidates(
    request: CandidateDetectionRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Detect potential candidates from one patient's canonical data."""

    run_id = _DETECTION_RUN_ID.get() or str(uuid4())
    started = time.perf_counter()
    logger.info(
        "Detection timing run_id=%s stage=endpoint_started",
        run_id,
    )

    context_started = time.perf_counter()
    try:
        context = get_patient_context(
            db=db,
            patient_id=request.patient_id,
        )
    except CanonicalPatientNotFoundError as exc:
        logger.warning(
            "Detection timing run_id=%s stage=patient_context_not_found source_count=0 elapsed_ms=%.0f",
            _DETECTION_RUN_ID.get() or "untracked",
            (time.perf_counter() - context_started) * 1000,
        )
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.error(
            "Detection timing run_id=%s stage=patient_context_failed source_count=0 elapsed_ms=%.0f error_type=%s",
            _DETECTION_RUN_ID.get() or "untracked",
            (time.perf_counter() - context_started) * 1000,
            type(exc).__name__,
        )
        raise
    logger.info(
        "Detection timing run_id=%s stage=patient_context_loaded source_count=%d elapsed_ms=%.0f",
        run_id,
        sum(len(context.get(key, [])) for key in ("conditions", "observations", "lab_results", "clinical_documents", "encounters")),
        (time.perf_counter() - context_started) * 1000,
    )

    normalized_patient = canonical_context_to_detection_input(context)

    uploaded_document_count = sum(
        1
        for document in context.get("clinical_documents", [])
        if (document.get("provenance") or {}).get("source") == "document_upload"
    )
    document_processing_started = time.perf_counter()
    try:
        documents = process_documents(context.get("clinical_documents", []), run_id=run_id)
    except Exception as exc:
        logger.error(
            "Detection timing run_id=%s stage=document_processing_failed source_count=%d elapsed_ms=%.0f error_type=%s",
            run_id, len(context.get("clinical_documents", [])),
            (time.perf_counter() - document_processing_started) * 1000,
            type(exc).__name__,
        )
        raise
    logger.info(
        "Detection timing run_id=%s stage=document_processing_complete provider=local_ocr model=local source_count=%d elapsed_ms=%.0f",
        run_id,
        len(documents),
        (time.perf_counter() - document_processing_started) * 1000,
    )

    documents_with_text = [
        document
        for document in documents
        if isinstance(document.get("text"), str)
        and document["text"].strip()
    ]
    # AI extraction is for free-text clinical documents. Structured records
    # remain available to the direct structured trigger matcher below.
    ai_sources = documents_with_text

    document_evidence: list[dict[str, Any]] = []
    document_evidence_error: str | None = None

    if not ai_sources:
        document_evidence_status = "no_document_text"
        logger.warning(
            "No readable clinical note text for AI analysis | run_id=%s | uploaded documents=%d | processed documents=%d",
            run_id,
            uploaded_document_count,
            len(documents),
        )
    else:
        logger.info(
            "Clinical note evidence ready for AI analysis | run_id=%s | note documents=%d | total characters=%d",
            run_id,
            len(documents_with_text),
            sum(len(document["text"]) for document in ai_sources),
        )
        evidence_started = time.perf_counter()
        try:
            document_evidence = extract_evidence(
                ai_sources,
                run_id=run_id,
            )
            document_evidence_status = "completed"
            logger.info(
                "Detection timing run_id=%s stage=evidence_extraction_complete source_count=%d elapsed_ms=%.0f evidence_count=%d",
                run_id, len(ai_sources), (time.perf_counter() - evidence_started) * 1000, len(document_evidence),
            )
            logger.info(
                "AI clinical evidence analysis completed | run_id=%s | evidence items=%d",
                run_id,
                len(document_evidence),
            )

        except DocumentAIUnavailableError as exc:
            logger.error(
                "Detection timing run_id=%s stage=evidence_extraction_failed source_count=%d elapsed_ms=%.0f error_type=%s",
                run_id, len(ai_sources), (time.perf_counter() - evidence_started) * 1000, type(exc).__name__,
            )
            logger.error(
                "Document processing could not take place | run_id=%s | both AI models are unavailable.",
                run_id,
            )
            document_evidence_status = "failed"
            document_evidence_error = _document_ai_error_message(exc)

        except RuntimeError as exc:
            logger.error(
                "Detection timing run_id=%s stage=evidence_extraction_failed source_count=%d elapsed_ms=%.0f error_type=%s",
                run_id, len(ai_sources), (time.perf_counter() - evidence_started) * 1000, type(exc).__name__,
            )
            logger.error("Detection checkpoint run_id=%s stage=document_evidence_failed category=configuration error_type=%s", run_id, type(exc).__name__)
            document_evidence_status = "failed"
            document_evidence_error = _document_ai_error_message(exc)

        except Exception as exc:
            logger.error(
                "Detection timing run_id=%s stage=evidence_extraction_failed source_count=%d elapsed_ms=%.0f error_type=%s",
                run_id, len(ai_sources), (time.perf_counter() - evidence_started) * 1000, type(exc).__name__,
            )
            logger.error("Detection checkpoint run_id=%s stage=document_evidence_failed category=provider_or_parse error_type=%s", run_id, type(exc).__name__)
            document_evidence_status = "failed"
            document_evidence_error = _document_ai_error_message(exc)

    try:
        matching_started = time.perf_counter()
        result = detect_candidates(
            normalized_patient,
            document_evidence=document_evidence,
        )
        logger.info(
            "Detection timing run_id=%s stage=candidate_matching_complete source_count=%d elapsed_ms=%.0f signal_count=%d candidate_count=%d",
            run_id, len(normalized_patient.get("conditions", [])) + len(normalized_patient.get("observations", [])) + len(normalized_patient.get("diagnostic_reports", [])) + len(document_evidence),
            (time.perf_counter() - matching_started) * 1000,
            result.get("signal_count", 0), result.get("candidate_count", 0),
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
        result["ai_evidence_source_count"] = len(ai_sources)
        result["ai_evidence_source_types"] = sorted({
            str(source.get("document_type") or "ClinicalDocument")
            for source in ai_sources
        })
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
            persistence_started = time.perf_counter()
            try:
                persisted_candidates = persist_detection_candidates(db, result, run_id=run_id)
            finally:
                logger.info(
                    "Detection timing run_id=%s stage=candidate_persistence_finished source_count=%d elapsed_ms=%.0f",
                    run_id, len(result.get("candidates", [])), (time.perf_counter() - persistence_started) * 1000,
                )
            result["candidates"] = [
                {
                    **candidate,
                    "candidate_id": candidate_row.candidate_id,
                    "case_id": candidate_row.case_id,
                    "status": candidate_row.status,
                }
                for candidate_row, candidate in zip(
                    persisted_candidates,
                    result["candidates"],
                    strict=True,
                )
            ]
            audit_started = time.perf_counter()
            try:
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
                        new_value=_without_persisted_scores(result),
                        metadata={"workflow_stage": "DETECTION"},
                        event_timestamp=completed_at,
                    ),
                    db,
                )
            finally:
                logger.info(
                    "Detection timing run_id=%s stage=audit_write_finished source_count=1 elapsed_ms=%.0f",
                    run_id, (time.perf_counter() - audit_started) * 1000,
                )
            result["detection_run"]["audit_id"] = audit_record.audit_id

        logger.info(
            "Detection timing run_id=%s stage=pipeline_complete status=%s source_count=%d elapsed_ms=%.0f",
            run_id,
            result["detection_run"]["status"],
            len(result["candidates"]),
            (time.perf_counter() - started) * 1000,
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
            "backend machine can reach the provider. Structured record detection may still complete. "
            "Search backend/logs/ai_detection.log for the run ID shown below."
        )
    busy_markers = (
        "429", "529", "rate limit", "rate_limit", "too many requests",
        "overloaded", "model is busy", "temporarily unavailable",
        "server overloaded", "capacity", "503",
    )
    if any(marker in message for marker in busy_markers):
        return (
            "The AI model is busy or rate limited, so clinical evidence analysis did not "
            "finish. Try detection again shortly; "
            "structured record detection may still have completed."
        )
    if any(marker in message for marker in ("api key", "api_key", "unauthorized", "permission denied", "403")):
        return (
            "The AI provider rejected the configured credentials or model access. "
            "Check the local provider key and selected model, then restart the backend. "
            "Structured record detection may still have completed."
        )
    if any(marker in message for marker in ("model not found", "not found", "404", "unsupported model")):
        return (
            "The configured AI model is unavailable to this provider account. "
            "Select a currently available model in the local environment and restart the backend. "
            "Structured record detection may still have completed."
        )
    detail = " ".join(str(exc).split())
    for secret in (
        settings.gemini_api_key,
        settings.groq_api_key,
        settings.groq_run_detection_api_key,
        settings.groq_anatomy_api_key,
        settings.openrouter_api_key,
    ):
        if secret:
            detail = detail.replace(secret, "[redacted]")
    detail = detail[:240]
    if detail:
        return (
            f"AI clinical evidence analysis failed ({type(exc).__name__}: {detail}). "
            "Search backend/logs/ai_detection.log for the run ID; "
            "structured record detection may still have completed."
        )
    return (
        "AI clinical evidence analysis failed. Try again or check the "
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
