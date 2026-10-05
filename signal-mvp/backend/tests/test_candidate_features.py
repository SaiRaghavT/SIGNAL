from backend.app.detection.candidate_fusion.ml.features import (
    extract_candidate_features,
)


def test_extract_candidate_features():
    signals = [
        {
            "patient_id": "PAT-001",
            "disease_id": "measles",
            "encounter_id": "ENC-001",
            "trigger_type": "CONDITION_CODE",
            "confidence": 1.0,
            "evidence": {
                "source_type": "Condition",
            },
        },
        {
            "patient_id": "PAT-001",
            "disease_id": "measles",
            "encounter_id": "ENC-001",
            "trigger_type": "LAB_RESULT",
            "confidence": 1.0,
            "evidence": {
                "source_type": "DiagnosticReport",
            },
        },
        {
            "patient_id": "PAT-001",
            "disease_id": "measles",
            "encounter_id": "ENC-001",
            "trigger_type": "LAB_RESULT",
            "confidence": 1.0,
            "evidence": {
                "source_type": "DiagnosticReport",
            },
        },
    ]

    features = extract_candidate_features(signals)

    assert features["condition_signal_present"] == 1
    assert features["lab_signal_present"] == 1
    assert features["document_signal_present"] == 0
    assert features["positive_lab_present"] == 1
    assert features["supporting_signal_count"] == 3
    assert features["evidence_source_count"] == 2
    assert features["max_signal_confidence"] == 1.0
    assert features["avg_signal_confidence"] == 1.0
    assert features["has_encounter"] == 1
    assert features["multiple_signal_types"] == 1