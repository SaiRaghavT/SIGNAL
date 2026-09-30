import pytest

from backend.app.detection.candidate_service import detect_candidates


def _trigger(resource_type, code, disease_id="measles"):
    return {
        "trigger_id": f"{resource_type.lower()}-{code}",
        "trigger_type": resource_type.upper(),
        "resource_type": resource_type,
        "code_system": "http://snomed.info/sct",
        "codes": [code],
        "disease_id": disease_id,
    }


def test_matching_condition_creates_candidate():
    patient = {
        "patient": {"id": "patient-001"},
        "conditions": [
            {
                "id": "condition-001",
                "patient_id": "patient-001",
                "encounter_id": "encounter-001",
                "system": "http://snomed.info/sct",
                "code": "condition-code",
                "display": "Measles",
            }
        ],
    }

    result = detect_candidates(
        patient,
        triggers=[_trigger("Condition", "condition-code")],
    )

    assert result["signal_count"] == 1
    assert result["candidate_count"] == 1
    candidate = result["candidates"][0]
    assert candidate["patient_id"] == "patient-001"
    assert candidate["disease_id"] == "measles"
    assert candidate["status"] == "POTENTIAL"
    assert candidate["evidence"][0]["code"] == "condition-code"


def test_matching_lab_observation_creates_candidate():
    patient = {
        "patient": {"id": "patient-002"},
        "observations": [
            {
                "id": "observation-001",
                "patient_id": "patient-002",
                "system": "http://snomed.info/sct",
                "code": "lab-code",
                "display": "Measles IgM",
            }
        ],
    }

    result = detect_candidates(
        patient,
        triggers=[_trigger("Observation", "lab-code")],
    )

    assert result["candidate_count"] == 1
    candidate = result["candidates"][0]
    assert candidate["disease_id"] == "measles"
    assert candidate["signals"][0]["trigger_type"] == "OBSERVATION"


def test_nonmatching_trigger_returns_no_candidates():
    patient = {
        "patient": {"id": "patient-003"},
        "conditions": [
            {
                "id": "condition-003",
                "patient_id": "patient-003",
                "system": "http://snomed.info/sct",
                "code": "hypertension-code",
                "display": "Hypertension",
            }
        ],
    }

    result = detect_candidates(
        patient,
        triggers=[_trigger("Condition", "measles-code")],
    )

    assert result["signal_count"] == 0
    assert result["candidate_count"] == 0
    assert result["candidates"] == []


def test_invalid_patient_input_is_rejected():
    with pytest.raises(ValueError, match="normalized_patient must be a dictionary"):
        detect_candidates(None)
