from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.canonical.query_service import (
    CanonicalPatientNotFoundError,
    get_patient_context,
)
from backend.app.database import get_db


router = APIRouter(
    prefix="/api/canonical",
    tags=["Canonical Data"],
)


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