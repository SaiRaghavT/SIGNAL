from types import SimpleNamespace

from backend.app.provenance.provenance import get_provenance


def test_patient_provenance():

    patient = SimpleNamespace(
        source_patient_id="patient-001",
        source="synthea",
        source_resource="Patient",
    )

    result = get_provenance(
        patient,
        "Patient",
    )

    assert result == {
        "entity_type": "Patient",
        "source": "synthea",
        "source_id": "patient-001",
        "source_resource": "Patient",
    }


def test_observation_provenance():

    observation = SimpleNamespace(
        source_observation_id="observation-001",
        source="synthea",
        source_resource="Observation",
    )

    result = get_provenance(
        observation,
        "Observation",
    )

    assert result == {
        "entity_type": "Observation",
        "source": "synthea",
        "source_id": "observation-001",
        "source_resource": "Observation",
    }