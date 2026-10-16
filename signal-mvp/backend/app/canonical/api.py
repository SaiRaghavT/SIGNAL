import hashlib
import time
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.anatomy.llm import derive_anatomy_findings_with_llm
from backend.app.anatomy.service import (
    collect_anatomy_evidence,
    derive_anatomy_findings,
)
from backend.app.ai_detection_logging import get_ai_detection_logger
from backend.app.canonical.query_service import (
    CanonicalPatientNotFoundError,
    get_patient_context,
    list_patients,
)
from backend.app.database import engine, get_db
from backend.app.detection.run_lock import try_acquire_patient_anatomy_lease
from backend.app.schemas.canonical import PatientListResponse


router = APIRouter(
    prefix="/api/canonical",
    tags=["Canonical Data"],
)

logger = get_ai_detection_logger()


@router.get("/patients", response_model=PatientListResponse)
def get_canonical_patients(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    search: str | None = Query(default=None, max_length=200),
    facility: str | None = Query(default=None, max_length=255),
    condition: str | None = Query(default=None, max_length=100),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        return list_patients(
            db=db,
            page=page,
            page_size=page_size,
            search=search,
            facility=facility,
            condition=condition,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve canonical patients.",
        ) from exc


@router.get("/patients/{patient_id}")
def get_canonical_patient(
    patient_id: UUID,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        return get_patient_context(
            db=db,
            patient_id=patient_id,
        )

    except CanonicalPatientNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve canonical patient context.",
        ) from exc


@router.get("/patients/{patient_id}/anatomy")
def get_canonical_patient_anatomy(
    patient_id: UUID,
    refresh: bool = Query(False),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return backend-extracted, source-linked findings for the anatomy view."""
    started = time.perf_counter()
    run_id = str(uuid4())
    patient_token = hashlib.sha256(str(patient_id).encode("utf-8")).hexdigest()[:16]
    lease = None
    skip_llm_reason: str | None = None
    try:
        lock_started = time.perf_counter()
        try:
            lease = try_acquire_patient_anatomy_lease(engine, patient_id)
        except Exception as exc:
            # The anatomy display can still use its local extractor if
            # coordination is unavailable; never duplicate an AI call blindly.
            skip_llm_reason = "lock_unavailable"
            logger.warning(
                "Anatomy timing run_id=%s patient_key=%s stage=lock_unavailable error_type=%s elapsed_ms=%.0f",
                run_id, patient_token, type(exc).__name__,
                (time.perf_counter() - lock_started) * 1000,
            )
        else:
            if lease is None:
                skip_llm_reason = "run_already_active"
                logger.info(
                    "Anatomy timing run_id=%s patient_key=%s stage=lock_conflict elapsed_ms=%.0f",
                    run_id, patient_token, (time.perf_counter() - lock_started) * 1000,
                )
            else:
                logger.info(
                    "Anatomy timing run_id=%s patient_key=%s stage=lock_acquired elapsed_ms=%.0f",
                    run_id, patient_token, (time.perf_counter() - lock_started) * 1000,
                )

        context_started = time.perf_counter()
        context = get_patient_context(db=db, patient_id=patient_id)
        logger.info(
            "Anatomy timing run_id=%s patient_key=%s stage=patient_context_loaded elapsed_ms=%.0f",
            run_id, patient_token, (time.perf_counter() - context_started) * 1000,
        )
        evidence_started = time.perf_counter()
        anatomy_evidence = collect_anatomy_evidence(context)
        source_token = hashlib.sha256(
            "|".join(sorted(
                str(item.get("source_document_id") or item.get("document_id") or "")
                for item in anatomy_evidence
            )).encode("utf-8")
        ).hexdigest()[:16]
        logger.info(
            "Anatomy timing run_id=%s patient_key=%s stage=evidence_prepared source_count=%d source_id=%s elapsed_ms=%.0f",
            run_id, patient_token, len(anatomy_evidence), source_token,
            (time.perf_counter() - evidence_started) * 1000,
        )

        findings = None
        extraction_method = None
        if skip_llm_reason is None:
            llm_started = time.perf_counter()
            try:
                findings = derive_anatomy_findings_with_llm(
                    anatomy_evidence,
                    force_refresh=refresh,
                    patient_id=str(patient_id),
                    run_id=run_id,
                )
                extraction_method = "anatomy_llm" if findings else None
            except Exception as exc:
                logger.warning(
                    "Anatomy timing run_id=%s patient_key=%s stage=llm_failed source_count=%d source_id=%s error_type=%s elapsed_ms=%.0f",
                    run_id, patient_token, len(anatomy_evidence), source_token,
                    type(exc).__name__, (time.perf_counter() - llm_started) * 1000,
                )
                findings = None
            else:
                logger.info(
                    "Anatomy timing run_id=%s patient_key=%s stage=llm_complete source_count=%d source_id=%s finding_count=%d elapsed_ms=%.0f",
                    run_id, patient_token, len(anatomy_evidence), source_token,
                    len(findings or []), (time.perf_counter() - llm_started) * 1000,
                )
        else:
            logger.info(
                "Anatomy timing run_id=%s patient_key=%s stage=llm_skipped reason=%s source_count=%d source_id=%s",
                run_id, patient_token, skip_llm_reason, len(anatomy_evidence), source_token,
            )
        # A valid but empty LLM result is not useful when the local extractor
        # can still find explicitly located, model-supported findings.
        if not findings:
            fallback_started = time.perf_counter()
            findings = derive_anatomy_findings(anatomy_evidence)
            extraction_method = "local_extraction"
            logger.info(
                "Anatomy timing run_id=%s patient_key=%s stage=local_fallback source_count=%d source_id=%s finding_count=%d elapsed_ms=%.0f reason=%s",
                run_id, patient_token, len(anatomy_evidence), source_token,
                len(findings), (time.perf_counter() - fallback_started) * 1000,
                skip_llm_reason or "llm_unavailable_or_empty",
            )
        return {
            "patient_id": str(patient_id),
            "findings": findings,
            "extraction_method": extraction_method,
        }
    except CanonicalPatientNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Patient not found.") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to derive patient anatomy findings.") from exc
    finally:
        if lease is not None:
            try:
                lease.release()
            except Exception as exc:
                logger.error(
                    "Anatomy timing run_id=%s patient_key=%s stage=lock_release_failed error_type=%s",
                    run_id, patient_token, type(exc).__name__,
                )
        logger.info(
            "Anatomy timing run_id=%s patient_key=%s stage=endpoint_complete elapsed_ms=%.0f",
            run_id, patient_token, (time.perf_counter() - started) * 1000,
        )
