from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.ingestion.documents.service import ingest_document
from backend.app.ingestion.documents.validator import (
    DocumentValidationError,
)


router = APIRouter(
    prefix="/api/ingestion",
    tags=["Document Ingestion"],
)


UPLOAD_DIRECTORY = Path("data/documents")

UPLOAD_DIRECTORY.mkdir(
    parents=True,
    exist_ok=True,
)


@router.post("/documents")
async def ingest_document_api(
    file: UploadFile = File(...),
    patient_id: UUID = Form(...),
    source_document_id: str = Form(...),
    document_type: str | None = Form(None),
    title: str | None = Form(None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Upload and ingest an unstructured clinical document.

    Flow:

        Document Upload
              ↓
        Validation
              ↓
        Text Extraction
              ↓
        ClinicalDocument
              ↓
        PostgreSQL
    """

    # --------------------------------------------------
    # 1. Normalize input
    # --------------------------------------------------

    source_document_id = source_document_id.strip()

    document_type = (
        document_type.strip()
        if document_type
        else None
    )

    title = (
        title.strip()
        if title
        else None
    )

    # --------------------------------------------------
    # 2. Validate required fields
    # --------------------------------------------------

    if not source_document_id:
        raise HTTPException(
            status_code=400,
            detail="source_document_id cannot be empty.",
        )

    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="Document filename is required.",
        )

    # --------------------------------------------------
    # 3. Validate file extension
    # --------------------------------------------------

    file_extension = Path(
        file.filename
    ).suffix.lower()

    if file_extension not in {
        ".pdf",
        ".docx",
        ".txt",
    }:
        raise HTTPException(
            status_code=400,
            detail=(
                "Unsupported document format. "
                "Supported formats: PDF, DOCX, TXT."
            ),
        )

    # --------------------------------------------------
    # 4. Temporary upload path
    # --------------------------------------------------

    destination = (
        UPLOAD_DIRECTORY
        / f"{source_document_id}{file_extension}"
    )

    try:
        # --------------------------------------------------
        # 5. Read uploaded file
        # --------------------------------------------------

        contents = await file.read()

        if not contents:
            raise HTTPException(
                status_code=400,
                detail="Uploaded document is empty.",
            )

        destination.write_bytes(contents)

        # --------------------------------------------------
        # 6. Ingest document
        # --------------------------------------------------

        result = ingest_document(
            db=db,
            file_path=destination,
            patient_id=patient_id,
            source_document_id=source_document_id,
            document_type=document_type,
            title=title or file.filename,
            content_type=file.content_type,
            source="document_upload",
            source_resource="ClinicalDocument",
        )

        return result

    # --------------------------------------------------
    # 7. Validation errors
    # --------------------------------------------------

    except DocumentValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    # --------------------------------------------------
    # 8. Business / database validation errors
    # --------------------------------------------------

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    # --------------------------------------------------
    # 9. Preserve FastAPI errors
    # --------------------------------------------------

    except HTTPException:
        raise

    # --------------------------------------------------
    # 10. Unexpected errors
    # --------------------------------------------------

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Document ingestion failed: {exc}",
        ) from exc

    # --------------------------------------------------
    # 11. Remove temporary file
    # --------------------------------------------------

    finally:
        if destination.exists():
            destination.unlink()