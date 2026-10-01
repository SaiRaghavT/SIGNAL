from backend.app.detection.candidate_service import (
    detect_candidates,
)


def test_measles_condition_creates_candidate():

    normalized_patient = {
        "patient": {
            "id": "patient-001",
        },
        "conditions": [
            {
                "id": "condition-001",
                "display": "Measles",
            }
        ],
        "lab_results": [],
    }

    candidates = detect_candidates(
        normalized_patient
    )

    assert len(candidates) == 1

    assert candidates[0]["patient_id"] == (
        "patient-001"
    )

    assert candidates[0]["disease"] == "measles"

    assert candidates[0]["candidate_type"] == (
        "condition"
    )


def test_measles_lab_creates_candidate():

    normalized_patient = {
        "patient": {
            "id": "patient-002",
        },
        "conditions": [],
        "lab_results": [
            {
                "test_display": "Measles IgM",
                "test_code": "13950-1",
                "conclusion": "Positive",
            }
        ],
    }

    candidates = detect_candidates(
        normalized_patient
    )

    assert len(candidates) == 1

    assert candidates[0]["disease"] == "measles"

    assert candidates[0]["candidate_type"] == (
        "laboratory"
    )


def test_no_matching_triggers_returns_no_candidates():

    normalized_patient = {
        "patient": {
            "id": "patient-003",
        },
        "conditions": [
            {
                "id": "condition-003",
                "display": "Hypertension",
            }
        ],
        "lab_results": [
            {
                "test_display": "Hemoglobin",
                "test_code": "718-7",
                "conclusion": "Normal",
            }
        ],
    }

    candidates = detect_candidates(
        normalized_patient
    )

    assert candidates == []