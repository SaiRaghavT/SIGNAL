import pytest

from app.detection.structured_trigger import _create_lab_signal, detect_structured_triggers


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


@pytest.mark.parametrize(
    ("conclusion", "report_status", "classification", "eligible"),
    [
        ("Measles virus RNA detected", "final", "POSITIVE", True),
        ("not detected", "final", "NEGATIVE", False),
        (None, "preliminary", "PRELIMINARY", False),
        ("equivocal", "final", "EQUIVOCAL", False),
        ("indeterminate", "final", "INDETERMINATE", False),
        (None, "final", "UNKNOWN", False),
        ("positive", "cancelled", "UNKNOWN", False),
        ("positive", "unknown", "UNKNOWN", False),
    ],
)
def test_measles_rctc_lab_result_is_classified_before_eligibility(
    conclusion, report_status, classification, eligible
):
    result = detect_structured_triggers({
        "patient": {"id": "patient-001"},
        "diagnostic_reports": [{
            "id": "lab-001",
            "patient_id": "patient-001",
            "encounter_id": "encounter-001",
            "test": {
                "system": "http://loinc.org",
                "code": "48508-6",
                "display": "Measles virus RNA [Presence] in Specimen by NAA",
            },
            "report_status": report_status,
            "conclusion": conclusion,
            "observations": [],
        }],
    })

    assert len(result) == 1
    signal = result[0]
    assert signal["trigger_type"] == "LAB_RESULT"
    assert signal["evidence"]["result_classification"] == classification
    assert signal["evidence"]["positive_detection_eligible"] is eligible
    assert signal["detection_priority"] == ("HIGHEST" if eligible else "REVIEW_ONLY")
    assert signal["evidence"]["code"] == "48508-6"
    assert signal["evidence"]["source_id"] == "lab-001"
    assert signal["evidence"]["disease_specific_test_mapping"] is True


def test_unmapped_measles_lab_code_does_not_create_trigger():
    result = detect_structured_triggers({
        "patient": {"id": "patient-001"},
        "diagnostic_reports": [{
            "id": "unknown-lab",
            "patient_id": "patient-001",
            "test": {"system": "http://loinc.org", "code": "UNMAPPED", "display": "Measles test"},
            "report_status": "final",
            "conclusion": "positive",
            "observations": [],
        }],
    })
    assert result == []


def test_measles_test_mapping_uses_verified_value_set_url_not_its_display_name():
    signal = _create_lab_signal(
        {"patient_id": "patient-001", "conclusion": "positive", "report_status": "final"},
        {"resource_type": "DiagnosticReport", "system": "http://loinc.org", "code": "48508-6", "display": "Measles RNA"},
        {
            "group": "LAB_RESULT",
            "group_id": "test-group",
            "disease_id": "http://snomed.info/sct|14189004",
            "value_set_urls": ["https://example.org/unverified-measles-tests"],
            "value_sets": [{"title": "Measles tests for measles virus"}],
        },
    )
    assert signal["evidence"]["result_classification"] == "POSITIVE"
    assert signal["evidence"]["disease_specific_test_mapping"] is False
    assert signal["evidence"]["positive_detection_eligible"] is False
