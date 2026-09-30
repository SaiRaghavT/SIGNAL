from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.ingestion.fhir.batch_service import ingest_fhir_bundles
from backend.app.ingestion.fhir.service import ingest_fhir_bundle
from backend.app.ingestion.fhir.validator import FHIRValidationError


router = APIRouter(
    prefix="/api/ingestion",
    tags=["FHIR Ingestion"],
)


class FHIRBatchRequest(BaseModel):
    bundles: list[dict[str, Any]]


@router.post("/fhir")
def ingest_fhir(
    payload: dict[str, Any],
    source: str = Query(
        default="fhir",
        description=(
            "Source system of the FHIR Bundle, "
            "e.g. synthea, epic, hapi_fhir"
        ),
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Ingest a single FHIR Bundle into the SIGNAL
    canonical database.
    """

    try:
        result = ingest_fhir_bundle(
            db=db,
            payload=payload,
            source=source,
        )

        return result

    except FHIRValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="FHIR Bundle ingestion failed.",
        ) from exc


@router.post("/fhir/batch")
def ingest_fhir_batch(
    request: FHIRBatchRequest,
    source: str = Query(
        default="fhir",
        description=(
            "Source system of the FHIR Bundles, "
            "e.g. synthea, epic, hapi_fhir"
        ),
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Ingest multiple FHIR Bundles into the SIGNAL
    canonical database.
    """

    try:
        return ingest_fhir_bundles(
            db=db,
            payloads=request.bundles,
            source=source,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="FHIR batch ingestion failed.",
        ) from exc