from pathlib import Path
from uuid import uuid4

from sqlalchemy import select

from backend.app.database import SessionLocal
from backend.app.ingestion.documents.service import ingest_document
from backend.app.models.clinical_document import ClinicalDocument
from backend.app.models.patient import Patient


def _get_test_patient() -> Patient:
    db = SessionLocal()

    try:
        patient = (
            db.execute(
                select(Patient)
                .order_by(Patient.created_at)
            )
            .scalars()
            .first()
        )

        assert patient is not None, (
            "No patient exists in the database. "
            "Run Synthea/FHIR ingestion first."
        )

        return patient

    finally:
        db.close()


def test_ingest_txt_document(tmp_path: Path):
    patient = _get_test_patient()

    document_path = tmp_path / "clinical_note.txt"

    document_path.write_text(
        "Patient presented with fever and rash. "
        "Clinical note for document ingestion testing.",
        encoding="utf-8",
    )

    source_document_id = f"DOC-TEST-SERVICE-{uuid4()}"

    db = SessionLocal()

    try:
        result = ingest_document(
            db=db,
            file_path=document_path,
            patient_id=patient.patient_id,
            source_document_id=source_document_id,
            document_type="clinical-note",
            title="Clinical Note Test",
            content_type="text/plain",
        )

        assert result["status"] == "success"

        assert result["patient_id"] == str(
            patient.patient_id
        )

        assert result["source_document_id"] == (
            source_document_id
        )

        assert result["text_length"] > 0

        document = (
            db.execute(
                select(ClinicalDocument).where(
                    ClinicalDocument.source_document_id
                    == source_document_id
                )
            )
            .scalars()
            .first()
        )

        assert document is not None

        assert document.patient_id == (
            patient.patient_id
        )

        assert (
            document.extracted_text
            == "Patient presented with fever and rash. "
            "Clinical note for document ingestion testing."
        )

    finally:
        db.query(ClinicalDocument).filter(
            ClinicalDocument.source_document_id == source_document_id
        ).delete(synchronize_session=False)
        db.commit()
        db.close()


def test_duplicate_document_is_idempotent(
    tmp_path: Path,
):
    patient = _get_test_patient()

    document_path = tmp_path / "duplicate.txt"

    document_path.write_text(
        "Duplicate document test.",
        encoding="utf-8",
    )

    source_document_id = f"DOC-TEST-IDEMPOTENCY-{uuid4()}"

    db = SessionLocal()

    try:
        first_result = ingest_document(
            db=db,
            file_path=document_path,
            patient_id=patient.patient_id,
            source_document_id=source_document_id,
            content_type="text/plain",
        )

        second_result = ingest_document(
            db=db,
            file_path=document_path,
            patient_id=patient.patient_id,
            source_document_id=source_document_id,
            content_type="text/plain",
        )

        assert first_result["status"] == "success"

        assert second_result["status"] == (
            "already_exists"
        )

        assert second_result["document_id"] == (
            first_result["document_id"]
        )

    finally:
        db.query(ClinicalDocument).filter(
            ClinicalDocument.source_document_id == source_document_id
        ).delete(synchronize_session=False)
        db.commit()
        db.close()


def test_missing_patient_is_rejected(
    tmp_path: Path,
):
    document_path = tmp_path / "missing_patient.txt"

    document_path.write_text(
        "This document should not be persisted.",
        encoding="utf-8",
    )

    source_document_id = f"DOC-TEST-MISSING-PATIENT-{uuid4()}"
    db = SessionLocal()

    try:
        try:
            ingest_document(
                db=db,
                file_path=document_path,
                patient_id=uuid4(),
                source_document_id=source_document_id,
                content_type="text/plain",
            )

            assert False, (
                "Expected missing patient to be rejected."
            )

        except ValueError as exc:
            assert "Patient not found" in str(exc)

        document = (
            db.execute(
                select(ClinicalDocument).where(
                    ClinicalDocument.source_document_id
                    == source_document_id
                )
            )
            .scalars()
            .first()
        )

        assert document is None

    finally:
        db.query(ClinicalDocument).filter(
            ClinicalDocument.source_document_id == source_document_id
        ).delete(synchronize_session=False)
        db.commit()
        db.close()
