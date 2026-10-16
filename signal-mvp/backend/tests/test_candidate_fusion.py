from app.detection.candidate_fusion import calculate_evidence_strength, fuse_candidate_signals


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


def test_same_disease_across_encounters_creates_one_patient_level_candidate():
    signals = [
        {
            "patient_id": "patient-001",
            "encounter_id": "encounter-initial",
            "disease_id": "measles",
            "trigger_concept_key": "measles",
            "trigger_type": "DOCUMENT_DIAGNOSIS",
            "evidence": {"source_type": "ClinicalDocument", "source_id": "note-initial"},
        },
        {
            "patient_id": "patient-001",
            "encounter_id": "encounter-rash",
            "disease_id": "http://snomed.info/sct|14189004",
            "trigger_concept_key": "http://snomed.info/sct|14189004",
            "trigger_type": "DOCUMENT_DIAGNOSIS",
            "evidence": {"source_type": "ClinicalDocument", "source_id": "note-rash"},
        },
        {
            "patient_id": "patient-001",
            "encounter_id": "encounter-confirmation",
            "disease_id": "measles",
            "trigger_concept_key": "measles",
            "trigger_type": "LAB_RESULT",
            "detection_priority": "HIGHEST",
            "evidence": {
                "source_type": "DiagnosticReport",
                "source_id": "lab-positive",
                "positive_detection_eligible": True,
                "disease_specific_test_mapping": True,
            },
        },
    ]

    result = fuse_candidate_signals(signals)

    assert len(result) == 1
    assert result[0]["encounter_id"] is None
    assert {signal["encounter_id"] for signal in result[0]["signals"]} == {
        "encounter-initial", "encounter-rash", "encounter-confirmation",
    }
    assert result[0]["detection_priority"] == "HIGHEST"


def test_model_confidence_is_not_returned_as_a_candidate_score():
    signals = [
        {
            "patient_id": "patient-001",
            "encounter_id": "encounter-001",
            "disease_id": "disease-001",
            "trigger_type": "CONDITION_CODE",
            "trigger_id": "condition-1",
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
    assert "confidence" not in result[0]
    assert "confidence_components" not in result[0]
    assert result[0]["evidence_strength"] == 60.0
    assert result[0]["evidence_strength_method"] == "weighted_rule_based_v2"


def test_qualifying_laboratory_trigger_has_separate_highest_priority():
    signals = [{
        "patient_id": "patient-001", "encounter_id": "encounter-001", "disease_id": "measles",
        "trigger_type": "LAB_RESULT", "detection_priority": "HIGHEST",
        "evidence": {"source_type": "DiagnosticReport", "source_id": "lab-1", "positive_detection_eligible": True, "disease_specific_test_mapping": True},
    }]
    candidate = fuse_candidate_signals(signals)[0]
    assert candidate["detection_priority"] == "HIGHEST"
    assert "confidence" not in candidate
    assert candidate["evidence_strength"] == 100.0


def test_highest_priority_positive_lab_scores_100_even_with_legacy_trigger_alias():
    score = calculate_evidence_strength([{
        "disease_id": "measles",
        "trigger_type": "LABORATORY_SIGNAL",
        "detection_priority": "HIGHEST",
        "evidence": {"positive_detection_eligible": True, "source_id": "lab-1"},
    }])
    assert score["score"] == 100.0
    assert score["components"][0]["factor"] == "primary_qualifying_laboratory"


def test_shared_concept_key_fuses_legacy_disease_labels_into_one_candidate():
    signals = [
        {
            "patient_id": "patient-001", "encounter_id": None,
            "disease_id": "Measles virus RNA [Presence] in Specimen by NAA",
            "trigger_concept_key": "http://snomed.info/sct|14189004",
            "trigger_type": "LAB_RESULT", "detection_priority": "HIGHEST",
            "evidence": {"source_id": "lab-1", "positive_detection_eligible": True},
        },
        {
            "patient_id": "patient-001", "encounter_id": None,
            "disease_id": "Measles", "trigger_concept_key": "measles",
            "trigger_type": "DOCUMENT_DIAGNOSIS",
            "evidence": {"source_id": "note-1", "evidence_type": "diagnosis"},
        },
    ]
    candidates = fuse_candidate_signals(signals)
    assert len(candidates) == 1
    assert candidates[0]["disease_id"] == "http://snomed.info/sct|14189004"
    assert candidates[0]["evidence_strength"] == 100.0


def test_nonqualifying_lab_does_not_add_evidence_strength():
    lab = {"trigger_type": "LAB_RESULT", "evidence": {"positive_detection_eligible": False, "source_id": "lab-1"}}
    assert calculate_evidence_strength([lab])["score"] == 0.0


def test_repeated_source_does_not_inflate_score_and_source_bonus_is_capped():
    signals = [
        {"trigger_type": "CONDITION_CODE", "trigger_id": "c", "evidence": {"source_id": "same"}},
        {"trigger_type": "CONDITION_CODE", "trigger_id": "c", "evidence": {"source_id": "same"}},
        *[{"trigger_type": "CONDITION_CODE", "trigger_id": "c", "evidence": {"source_id": f"s{i}"}} for i in range(6)],
    ]
    result = calculate_evidence_strength(signals)
    assert result["score"] == 75.0


def test_missing_source_ids_do_not_create_distinct_record_bonus():
    result = calculate_evidence_strength([
        {"trigger_type": "CONDITION_CODE", "trigger_id": "c", "evidence": {}},
        {"trigger_type": "CONDITION_CODE", "trigger_id": "c", "evidence": {}},
    ])
    assert result["score"] == 60.0


def test_unmatched_source_document_does_not_add_support_strength():
    result = calculate_evidence_strength([
        {"trigger_type": "CONDITION_CODE", "trigger_id": "c", "evidence": {"source_id": "condition-1"}},
        {"trigger_type": "DOCUMENT_EVIDENCE", "evidence": {
            "source_id": "note-1", "source_type": "document",
            "evidence_role": "supporting_clinical_evidence",
        }},
    ])
    assert result["score"] == 60.0


def test_source_linked_document_quote_adds_bonus_and_score_is_capped():
    signals = [
        {"trigger_type": "CONDITION_CODE", "trigger_id": "c", "evidence": {"source_type": "Condition", "source_id": f"s{i}"}}
        for i in range(8)
    ] + [{"trigger_type": "DOCUMENT_EVIDENCE", "evidence": {"source_type": "document", "source_id": "doc", "evidence_text": "quoted text"}}]
    result = calculate_evidence_strength(signals)
    assert result["score"] == 90.0


def test_lab_without_authoritative_eligibility_does_not_get_perfect_score():
    result = calculate_evidence_strength([{
        "disease_id": "http://snomed.info/sct|14189004",
        "trigger_type": "LAB_RESULT",
        "evidence": {
            "source_id": "lab-1",
            "positive_detection_eligible": False,
            "disease_specific_test_mapping": False,
        },
    }])
    assert result["score"] == 0.0


def test_configured_structured_trigger_uses_60_point_base():
    score = calculate_evidence_strength([{
        "trigger_id": "configured-measles-condition",
        "trigger_type": "CONDITION_CODE",
        "evidence": {"source_type": "Condition", "source_id": "condition-1"},
    }])
    assert score["score"] == 60.0
    assert score["components"][0]["points"] == 60.0


def test_disease_linked_document_trigger_uses_50_point_base_and_quote_bonus():
    score = calculate_evidence_strength([{
        "trigger_id": "document-measles",
        "trigger_type": "DOCUMENT_DIAGNOSIS",
        "evidence": {
            "source_type": "ClinicalDocument", "source_id": "doc-1",
            "evidence_text": "Measles diagnosis confirmed.",
        },
    }])
    assert score["score"] == 60.0
    assert [item["points"] for item in score["components"][:2]] == [50.0, 10.0]


def test_one_and_multiple_distinct_symptoms_use_separate_configured_bases():
    one = calculate_evidence_strength([{
        "trigger_type": "DOCUMENT_EVIDENCE",
        "evidence": {"source_type": "ClinicalDocument", "source_id": "doc-1", "evidence_type": "symptom", "concept": "Rash", "assertion": "present"},
    }])
    many = calculate_evidence_strength([
        {"trigger_type": "DOCUMENT_EVIDENCE", "evidence": {"source_type": "ClinicalDocument", "source_id": "doc-1", "evidence_type": "symptom", "concept": concept, "assertion": "present"}}
        for concept in ("Rash", "Cough")
    ])
    assert one["score"] == 25.0
    assert many["score"] == 40.0


def test_present_exposure_uses_configured_35_point_base():
    score = calculate_evidence_strength([{
        "trigger_type": "DOCUMENT_EVIDENCE",
        "evidence": {"source_type": "ClinicalDocument", "source_id": "doc-1", "evidence_type": "exposure", "concept": "Measles contact", "assertion": "present"},
    }])
    assert score["score"] == 35.0


def test_absent_or_historical_symptom_does_not_score_as_positive():
    score = calculate_evidence_strength([{
        "trigger_type": "DOCUMENT_EVIDENCE",
        "evidence": {"source_type": "ClinicalDocument", "source_id": "doc-1", "evidence_type": "symptom", "concept": "Rash", "assertion": "absent"},
    }])
    assert score["score"] == 0.0


def test_distinct_sources_are_deduplicated_across_signal_types_and_missing_ids():
    score = calculate_evidence_strength([
        {"trigger_id": "c1", "trigger_type": "CONDITION_CODE", "evidence": {"source_type": "Condition", "source_id": "shared"}},
        {"trigger_type": "DOCUMENT_EVIDENCE", "evidence": {"source_type": "ClinicalDocument", "source_id": "shared", "evidence_type": "finding", "evidence_text": "quote"}},
        {"trigger_id": "c2", "trigger_type": "CONDITION_CODE", "evidence": {"source_type": "Condition"}},
    ])
    assert score["score"] == 75.0
    assert score["score"] <= 100


def test_nonqualifying_positive_lab_does_not_raise_structured_score():
    score = calculate_evidence_strength([
        {"trigger_id": "condition", "trigger_type": "CONDITION_CODE", "evidence": {"source_type": "Condition", "source_id": "c1"}},
        {"trigger_type": "LAB_RESULT", "evidence": {"source_id": "lab-1", "result_classification": "NEGATIVE", "positive_detection_eligible": False}},
    ])
    assert score["score"] == 60.0


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
