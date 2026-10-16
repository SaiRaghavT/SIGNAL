from app.detection.candidate_service import detect_candidates


def test_no_matching_triggers_returns_no_candidates():
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

    result = detect_candidates(
        normalized_patient,
        triggers=triggers,
    )

    assert result["patient_id"] == "patient-001"
    assert result["signal_count"] == 0
    assert result["candidate_count"] == 0
    assert result["signals"] == []
    assert result["candidates"] == []


def test_matching_trigger_produces_candidate():
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

    result = detect_candidates(
        normalized_patient,
        triggers=triggers,
    )

    assert result["patient_id"] == "patient-001"
    assert result["signal_count"] == 1
    assert result["candidate_count"] == 1

    candidate = result["candidates"][0]

    assert candidate["patient_id"] == "patient-001"
    assert candidate["encounter_id"] == "encounter-001"
    assert candidate["disease_id"] == "example-disease"
    assert candidate["status"] == "POTENTIAL"
    assert len(candidate["evidence"]) == 1


def test_multiple_signals_are_fused_into_one_candidate():
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
        "observations": [
            {
                "id": "observation-001",
                "system": "http://loinc.org",
                "code": "789012",
                "display": "Example Laboratory Result",
                "patient_id": "patient-001",
            }
        ],
        "diagnostic_reports": [],
        "medications": [],
        "procedures": [],
        "encounters": [],
    }

    triggers = [
        {
            "trigger_id": "condition-trigger",
            "trigger_type": "CONDITION_CODE",
            "resource_type": "Condition",
            "code_system": "http://snomed.info/sct",
            "codes": ["123456"],
            "disease_id": "example-disease",
        },
        {
            "trigger_id": "lab-trigger",
            "trigger_type": "LAB_RESULT",
            "resource_type": "Observation",
            "code_system": "http://loinc.org",
            "codes": ["789012"],
            "disease_id": "example-disease",
        },
    ]

    result = detect_candidates(
        normalized_patient,
        triggers=triggers,
    )

    assert result["signal_count"] == 1
    assert result["candidate_count"] == 1
    assert len(result["laboratory_review_signals"]) == 1
    assert result["laboratory_review_signals"][0]["evidence"]["result_classification"] == "UNKNOWN"

    candidate = result["candidates"][0]

    assert candidate["status"] == "POTENTIAL"
    assert len(candidate["signals"]) == 2
    assert len(candidate["evidence"]) == 2


def test_invalid_normalized_patient_is_rejected():
    try:
        detect_candidates(None)
        assert False
    except ValueError as exc:
        assert str(exc) == "normalized_patient must be a dictionary."


def test_nonpositive_lab_result_is_review_evidence_not_a_candidate():
    result = detect_candidates({
        "patient": {"id": "patient-001"},
        "conditions": [],
        "observations": [],
        "diagnostic_reports": [{
            "id": "lab-negative",
            "patient_id": "patient-001",
            "encounter_id": "encounter-001",
            "test": {"system": "http://loinc.org", "code": "48508-6", "display": "Measles virus RNA"},
            "report_status": "final",
            "conclusion": "not detected",
            "observations": [],
        }],
        "medications": [], "procedures": [], "encounters": [], "clinical_documents": [],
    })
    assert result["candidate_count"] == 0
    assert result["laboratory_review_signals"][0]["evidence"]["result_classification"] == "NEGATIVE"


def test_qualifying_measles_lab_result_creates_high_priority_candidate():
    result = detect_candidates({
        "patient": {"id": "patient-001"},
        "conditions": [], "observations": [],
        "diagnostic_reports": [{
            "id": "lab-positive", "patient_id": "patient-001", "encounter_id": "encounter-001",
            "test": {"system": "http://loinc.org", "code": "48508-6", "display": "Measles virus RNA"},
            "report_status": "final", "conclusion": "positive", "observations": [],
        }],
        "medications": [], "procedures": [], "encounters": [], "clinical_documents": [],
    })
    assert result["candidate_count"] == 1
    candidate = result["candidates"][0]
    assert candidate["detection_priority"] == "HIGHEST"
    assert candidate["signals"][0]["evidence"]["positive_detection_eligible"] is True
    assert "confidence" not in candidate
    assert candidate["evidence_strength"] == 100.0
    assert candidate["evidence_strength_method"] == "weighted_rule_based_v2"
