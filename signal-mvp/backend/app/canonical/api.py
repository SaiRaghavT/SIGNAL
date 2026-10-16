from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.canonical.query_service import (
    CanonicalPatientNotFoundError,
    get_patient_context,
    list_patients,
)
from backend.app.database import get_db
from backend.app.schemas.canonical import PatientListResponse


router = APIRouter(
    prefix="/api/canonical",
    tags=["Canonical Data"],
)


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
