import pytest
from sqlalchemy import select

from backend.app.database import SessionLocal
from backend.app.models.patient import Patient
from backend.app.models.encounter import Encounter
from backend.app.models.condition import Condition
from backend.app.models.observation import Observation
from backend.app.models.lab_result import LabResult
from backend.app.models.clinical_document import ClinicalDocument
from backend.app.provenance.provenance import get_provenance


@pytest.mark.parametrize(
    "model,entity_type,source_id_field,expected_resource",
    [
        (
            Patient,
            "Patient",
            "source_patient_id",
            "Patient",
        ),
        (
            Encounter,
            "Encounter",
            "source_encounter_id",
            "Encounter",
        ),
        (
            Condition,
            "Condition",
            "source_condition_id",
            "Condition",
        ),
        (
            Observation,
            "Observation",
            "source_observation_id",
            "Observation",
        ),
        (
            LabResult,
            "LabResult",
            "source_lab_result_id",
            "DiagnosticReport",
        ),
        (
            ClinicalDocument,
            "ClinicalDocument",
            "source_document_id",
            "DocumentReference",
        ),
    ],
)
def test_real_canonical_provenance(
    model,
    entity_type,
    source_id_field,
    expected_resource,
):
    db = SessionLocal()

    try:
        entity = db.execute(
            select(model)
            .where(model.source == "synthea")
            .limit(1)
        ).scalar_one_or_none()

        assert entity is not None, (
            f"No Synthea {entity_type} found in the database."
        )

        result = get_provenance(
            entity,
            entity_type,
        )

        assert result["entity_type"] == entity_type
        assert result["source"] == "synthea"
        assert result["source_id"] == getattr(
            entity,
            source_id_field,
        )
        assert result["source_id"] is not None
        assert result["source_resource"] == expected_resource

    finally:
        db.close()