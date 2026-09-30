from app.detection.candidate_fusion import fuse_candidate_signals


def test_empty_signals_returns_empty_candidates():
    result = fuse_candidate_signals([])

    assert result == []


def test_multiple_signals_for_same_event_are_fused():
    signals = [
        {
            "patient_id": "patient-001",
            "encounter_id": "encounter-001",
            "disease_id": "disease-001",
            "trigger_type": "CONDITION_CODE",
            "confidence": 1.0,
            "detected_at": "2026-09-27T10:00:00+00:00",
            "evidence": {
                "source_type": "Condition",
                "source_id": "condition-001",
                "code": "123456",
            },
        },
        {
            "patient_id": "patient-001",
            "encounter_id": "encounter-001",
            "disease_id": "disease-001",
            "trigger_type": "LAB_RESULT",
            "confidence": 0.95,
            "detected_at": "2026-09-27T10:01:00+00:00",
            "evidence": {
                "source_type": "Observation",
                "source_id": "observation-001",
                "code": "789012",
            },
        },
    ]

    result = fuse_candidate_signals(signals)

    assert len(result) == 1

    candidate = result[0]

    assert candidate["patient_id"] == "patient-001"
    assert candidate["encounter_id"] == "encounter-001"
    assert candidate["disease_id"] == "disease-001"
    assert candidate["status"] == "POTENTIAL"
    assert len(candidate["evidence"]) == 2
    assert len(candidate["signals"]) == 2


def test_different_patients_create_separate_candidates():
    signals = [
        {
            "patient_id": "patient-001",
            "encounter_id": "encounter-001",
            "disease_id": "disease-001",
            "trigger_type": "CONDITION_CODE",
            "confidence": 1.0,
            "evidence": {
                "source_type": "Condition",
                "source_id": "condition-001",
            },
        },
        {
            "patient_id": "patient-002",
            "encounter_id": "encounter-001",
            "disease_id": "disease-001",
            "trigger_type": "CONDITION_CODE",
            "confidence": 1.0,
            "evidence": {
                "source_type": "Condition",
                "source_id": "condition-002",
            },
        },
    ]

    result = fuse_candidate_signals(signals)

    assert len(result) == 2


def test_different_diseases_create_separate_candidates():
    signals = [
        {
            "patient_id": "patient-001",
            "encounter_id": "encounter-001",
            "disease_id": "disease-001",
            "trigger_type": "CONDITION_CODE",
            "confidence": 1.0,
            "evidence": {
                "source_type": "Condition",
                "source_id": "condition-001",
            },
        },
        {
            "patient_id": "patient-001",
            "encounter_id": "encounter-001",
            "disease_id": "disease-002",
            "trigger_type": "CONDITION_CODE",
            "confidence": 1.0,
            "evidence": {
                "source_type": "Condition",
                "source_id": "condition-002",
            },
        },
    ]

    result = fuse_candidate_signals(signals)

    assert len(result) == 2


def test_highest_signal_confidence_is_preserved():
    signals = [
        {
            "patient_id": "patient-001",
            "encounter_id": "encounter-001",
            "disease_id": "disease-001",
            "trigger_type": "CONDITION_CODE",
            "confidence": 0.80,
            "evidence": {},
        },
        {
            "patient_id": "patient-001",
            "encounter_id": "encounter-001",
            "disease_id": "disease-001",
            "trigger_type": "LAB_RESULT",
            "confidence": 0.95,
            "evidence": {},
        },
    ]

    result = fuse_candidate_signals(signals)

    assert len(result) == 1
    assert result[0]["confidence"] == 0.95


def test_invalid_input_is_rejected():
    try:
        fuse_candidate_signals(None)
        assert False
    except ValueError as exc:
        assert str(exc) == "signals must be a list."


def test_invalid_signal_entries_are_ignored():
    signals = [
        None,
        "invalid",
        {
            "patient_id": "patient-001",
            "encounter_id": "encounter-001",
            "disease_id": "disease-001",
            "trigger_type": "CONDITION_CODE",
            "confidence": 1.0,
            "evidence": {},
        },
    ]

    result = fuse_candidate_signals(signals)

    assert len(result) == 1