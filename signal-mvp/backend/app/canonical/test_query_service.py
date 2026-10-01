from uuid import UUID

import pytest

from backend.app.canonical.query_service import (
    CanonicalPatientNotFoundError,
    get_patient_context,
)
from backend.app.database import SessionLocal


PATIENT_ID = UUID("40ab7b04-1246-4fa3-8ae2-df520124b47a")


def test_get_patient_context_returns_expected_structure():
    db = SessionLocal()

    try:
        context = get_patient_context(db, PATIENT_ID)

        assert "patient" in context
        assert "encounters" in context
        assert "conditions" in context
        assert "observations" in context
        assert "lab_results" in context
        assert "clinical_documents" in context

    finally:
        db.close()


def test_get_patient_context_returns_expected_counts():
    db = SessionLocal()

    try:
        context = get_patient_context(db, PATIENT_ID)

        assert context["patient"]["patient_id"] == str(PATIENT_ID)

        assert len(context["encounters"]) == 18
        assert len(context["conditions"]) == 25
        assert len(context["observations"]) == 116
        assert len(context["lab_results"]) == 37
        assert len(context["clinical_documents"]) == 22

    finally:
        db.close()


def test_patient_context_contains_provenance():
    db = SessionLocal()

    try:
        context = get_patient_context(db, PATIENT_ID)

        assert context["patient"]["provenance"]["source"] == "synthea"
        assert context["patient"]["provenance"]["source_resource"] == "Patient"

        assert context["encounters"][0]["provenance"]["source"] == "synthea"
        assert context["conditions"][0]["provenance"]["source"] == "synthea"

    finally:
        db.close()


def test_patient_context_contains_coded_condition():
    db = SessionLocal()

    try:
        context = get_patient_context(db, PATIENT_ID)

        condition = context["conditions"][0]

        assert "code" in condition
        assert condition["code"]["system"] is not None
        assert condition["code"]["code"] is not None
        assert condition["code"]["display"] is not None

    finally:
        db.close()


def test_nonexistent_patient_is_rejected():
    db = SessionLocal()

    try:
        with pytest.raises(CanonicalPatientNotFoundError):
            get_patient_context(
                db,
                UUID("00000000-0000-0000-0000-000000000000"),
            )

    finally:
        db.close()