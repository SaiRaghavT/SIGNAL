from app.detection.structured_trigger import detect_structured_triggers


def test_no_triggers_returns_empty_list():
    normalized_patient = {
        "patient": {
            "id": "patient-001"
        },
        "conditions": [],
        "observations": [],
        "diagnostic_reports": [],
        "medications": [],
        "procedures": [],
        "encounters": [],
    }

    result = detect_structured_triggers(normalized_patient)

    assert result == []


def test_condition_trigger_creates_candidate_signal():
    normalized_patient = {
        "patient": {
            "id": "patient-001"
        },
        "conditions": [
            {
                "id": "condition-001",
                "system": "http://snomed.info/sct",
                "code": "123456",
                "display": "Example Condition",
                "patient_id": "patient-001",
                "encounter_id": "encounter-001",
            }
        ],
        "observations": [],
        "diagnostic_reports": [],
        "medications": [],
        "procedures": [],
        "encounters": [],
    }

    triggers = [
        {
            "trigger_id": "example-condition",
            "trigger_type": "CONDITION_CODE",
            "resource_type": "Condition",
            "code_system": "http://snomed.info/sct",
            "codes": ["123456"],
            "disease_id": "example-disease",
        }
    ]

    result = detect_structured_triggers(
        normalized_patient,
        triggers=triggers,
    )

    assert len(result) == 1

    signal = result[0]

    assert signal["patient_id"] == "patient-001"
    assert signal["encounter_id"] == "encounter-001"
    assert signal["trigger_id"] == "example-condition"
    assert signal["trigger_type"] == "CONDITION_CODE"
    assert signal["disease_id"] == "example-disease"
    assert signal["confidence"] == 1.0


def test_non_matching_condition_does_not_create_candidate():
    normalized_patient = {
        "patient": {
            "id": "patient-001"
        },
        "conditions": [
            {
                "id": "condition-001",
                "system": "http://snomed.info/sct",
                "code": "999999",
                "display": "Unrelated Condition",
                "patient_id": "patient-001",
            }
        ],
        "observations": [],
    }

    triggers = [
        {
            "trigger_id": "example-condition",
            "trigger_type": "CONDITION_CODE",
            "resource_type": "Condition",
            "code_system": "http://snomed.info/sct",
            "codes": ["123456"],
            "disease_id": "example-disease",
        }
    ]

    result = detect_structured_triggers(
        normalized_patient,
        triggers=triggers,
    )

    assert result == []


def test_wrong_code_system_does_not_match():
    normalized_patient = {
        "patient": {
            "id": "patient-001"
        },
        "conditions": [
            {
                "id": "condition-001",
                "system": "http://example.org/system",
                "code": "123456",
                "display": "Example Condition",
                "patient_id": "patient-001",
            }
        ],
    }

    triggers = [
        {
            "trigger_id": "example-condition",
            "trigger_type": "CONDITION_CODE",
            "resource_type": "Condition",
            "code_system": "http://snomed.info/sct",
            "codes": ["123456"],
            "disease_id": "example-disease",
        }
    ]

    result = detect_structured_triggers(
        normalized_patient,
        triggers=triggers,
    )

    assert result == []


def test_invalid_input_is_rejected():
    try:
        detect_structured_triggers(None)
        assert False
    except ValueError as exc:
        assert str(exc) == "normalized_patient must be a dictionary."