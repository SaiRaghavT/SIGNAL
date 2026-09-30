from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.database import get_db

from .schemas import (
    AttestationRequest,
    AttestationResponse,
)
from .service import AttestationControlService


router = APIRouter(
    prefix="/api/agents/attestation",
    tags=["Attestation Control"],
)

service = AttestationControlService()


@router.post(
    "/validate",
    response_model=AttestationResponse,
)
def validate_attestation(
    request: AttestationRequest,
    db: Session = Depends(get_db),
) -> AttestationResponse:

    try:
        return service.validate(request, db)

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc