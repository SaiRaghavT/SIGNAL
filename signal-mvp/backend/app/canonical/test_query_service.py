from types import SimpleNamespace
from uuid import UUID

import pytest

from backend.app.canonical.query_service import (
    CanonicalPatientNotFoundError,
    get_patient_context,
)
from backend.app.models.clinical_document import ClinicalDocument
from backend.app.models.condition import Condition
from backend.app.models.encounter import Encounter
from backend.app.models.lab_result import LabResult
from backend.app.models.observation import Observation
from backend.app.models.patient import Patient


PATIENT_ID = UUID("40ab7b04-1246-4fa3-8ae2-df520124b47a")


class FakeQuery:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *_args):
        return self

    def order_by(self, *_args):
        return self

    def first(self):
        return self.rows[0] if self.rows else None

    def all(self):
        return self.rows


class FakeSession:
    def __init__(self, patient_exists=True):
        patient = SimpleNamespace(
            patient_id=PATIENT_ID,
            source_patient_id="synthea-001",
            first_name="Test",
            last_name="Patient",
            date_of_birth=None,
            sex="unknown",
            address_line="123 Main St",
            city="Austin",
            county="Travis",
            state="TX",
            postal_code="78701",
            source="synthea",
            source_resource="Patient",
        )
        self.rows = {
            Patient: [patient] if patient_exists else [],
            Encounter: [SimpleNamespace(
                encounter_id=UUID("00000000-0000-0000-0000-000000000001"),
                source_encounter_id="enc-001",
                patient_id=PATIENT_ID,
                facility_id=None,
                encounter_type="ambulatory",
                status="finished",
                start_time=None,
                end_time=None,
                source="synthea",
                source_resource="Encounter",
            )],
            Condition: [SimpleNamespace(
                condition_id=UUID("00000000-0000-0000-0000-000000000002"),
                source_condition_id="condition-001",
                patient_id=PATIENT_ID,
                encounter_id=None,
                condition_system="http://snomed.info/sct",
                condition_code="123",
                condition_display="Example condition",
                clinical_status="active",
                verification_status="confirmed",
                onset_time=None,
                recorded_time=None,
                source="synthea",
                source_resource="Condition",
            )],
            Observation: [],
            LabResult: [],
            ClinicalDocument: [],
        }

    def query(self, model):
        return FakeQuery(self.rows[model])


def test_get_patient_context_returns_canonical_structure_and_provenance():
    context = get_patient_context(FakeSession(), PATIENT_ID)

    assert set(context) == {
        "patient",
        "encounters",
        "conditions",
        "observations",
        "lab_results",
        "clinical_documents",
    }
    assert context["patient"]["patient_id"] == str(PATIENT_ID)
    assert context["patient"]["address"]["county"] == "Travis"
    assert context["patient"]["provenance"] == {
        "source": "synthea",
        "source_resource": "Patient",
    }
    assert context["encounters"][0]["provenance"]["source"] == "synthea"
    condition = context["conditions"][0]
    assert condition["code"] == {
        "system": "http://snomed.info/sct",
        "code": "123",
        "display": "Example condition",
    }


def test_nonexistent_patient_is_rejected():
    with pytest.raises(CanonicalPatientNotFoundError):
        get_patient_context(FakeSession(patient_exists=False), PATIENT_ID)
