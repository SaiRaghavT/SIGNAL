from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.ingestion.hl7.service import ingest_hl7_message


router = APIRouter(
    prefix="/api/ingestion",
    tags=["HL7 Ingestion"],
)


class HL7MessageRequest(BaseModel):
    message: str


@router.post("/hl7")
def ingest_hl7(
    request: HL7MessageRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Ingest one HL7 v2 message into SIGNAL.

    Flow:

        HL7 Message
             ↓
        Parser
             ↓
        Data Quality
             ↓
        Mapper
             ↓
        PostgreSQL
    """

    try:
        result = ingest_hl7_message(
            db=db,
            message=request.message,
        )

        return result

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="HL7 message ingestion failed.",
        ) from exc