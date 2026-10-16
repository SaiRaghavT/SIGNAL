from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from backend.app.ingestion.documents.extractor import (
    extract_text_from_file,
)
from backend.app.ingestion.documents.validator import (
    validate_document,
)
from backend.app.models.clinical_document import ClinicalDocument
from backend.app.models.patient import Patient


def ingest_document(
    db: Session,
    file_path: str | Path,
    patient_id: UUID,
    source_document_id: str,
    document_type: str | None = None,
    document_status: str | None = "current",
    title: str | None = None,
    content_type: str | None = None,
    source: str = "document_upload",
    source_resource: str = "ClinicalDocument",
) -> dict[str, Any]:
    """
    Validate, extract, and persist an unstructured clinical document.

    Flow:

        Document
           ↓
        Validation
           ↓
        Text Extraction
           ↓
        ClinicalDocument
           ↓
        PostgreSQL
    """

    try:
        # --------------------------------------------------
        # 1. Validate document
        # --------------------------------------------------

        validate_document(
            file_path=file_path,
            content_type=content_type,
        )

        # --------------------------------------------------
        # 2. Verify patient exists
        # --------------------------------------------------

        patient = (
            db.query(Patient)
            .filter(
                Patient.patient_id == patient_id
            )
            .first()
        )

        if patient is None:
            raise ValueError(
                f"Patient not found: {patient_id}"
            )

        # --------------------------------------------------
        # 3. Check for duplicate document
        # --------------------------------------------------

        existing_document = (
            db.query(ClinicalDocument)
            .filter(
                ClinicalDocument.source == source,
                ClinicalDocument.source_document_id
                == source_document_id,
            )
            .first()
        )

        if existing_document is not None:
            return {
                "status": "already_exists",
                "document_id": str(
                    existing_document.document_id
                ),
                "patient_id": str(
                    existing_document.patient_id
                ),
                "source": existing_document.source,
                "source_document_id": (
                    existing_document.source_document_id
                ),
                "text_length": len(
                    existing_document.extracted_text
                    or ""
                ),
            }

        # --------------------------------------------------
        # 4. Extract text
        # --------------------------------------------------

        extracted_text = extract_text_from_file(
            file_path=file_path,
            content_type=content_type,
        )

        # --------------------------------------------------
        # 5. Create canonical ClinicalDocument
        # --------------------------------------------------

        path = Path(file_path)

        document = ClinicalDocument(
            source_document_id=source_document_id,
            patient_id=patient.patient_id,
            encounter_id=None,
            document_type=document_type
            or path.suffix.lower().replace(".", ""),
            document_status=document_status,
            title=title or path.name,
            document_date=None,
            author_reference=None,
            content_type=content_type,
            content_location=str(path),
            extracted_text=extracted_text,
            source=source,
            source_resource=source_resource,
        )

        db.add(document)
        db.flush()
        db.refresh(document)

        # --------------------------------------------------
        # 6. Commit
        # --------------------------------------------------

        db.commit()

        # --------------------------------------------------
        # 7. Return result
        # --------------------------------------------------

        return {
            "status": "success",
            "document_id": str(
                document.document_id
            ),
            "patient_id": str(
                document.patient_id
            ),
            "source": document.source,
            "source_document_id": (
                document.source_document_id
            ),
            "document_type": (
                document.document_type
            ),
            "text_length": len(
                extracted_text
            ),
        }

    except Exception:
        db.rollback()
        raise