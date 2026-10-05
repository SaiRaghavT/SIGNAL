from backend.app.smart_field_population.mapper import populate_report_fields


def test_direct_field_mapping():
    candidate = {
        "candidate_id": "TEST-27-001",
        "disease": "measles",
        "patient": {
            "county": "Travis",
        },
    }

    result = populate_report_fields(candidate)

    assert result.fields["patient.county"] == "Travis"
    assert "patient.county" in result.populated_fields


def test_disease_maps_to_clinical_diagnosis():
    candidate = {
        "candidate_id": "TEST-27-002",
        "disease": "measles",
        "patient": {},
    }

    result = populate_report_fields(candidate)

    assert result.fields["clinical.diagnosis"] == "measles"
    assert "clinical.diagnosis" in result.populated_fields


def test_missing_required_fields_are_tracked():
    candidate = {
        "candidate_id": "TEST-27-003",
        "disease": "measles",
        "patient": {},
    }

    result = populate_report_fields(candidate)

    assert "patient.date_of_birth" in result.missing_fields
    assert "patient.date_of_birth" in result.required_missing_fields


def test_missing_optional_fields_are_not_required():
    candidate = {
        "candidate_id": "TEST-27-004",
        "disease": "measles",
        "patient": {},
    }

    result = populate_report_fields(candidate)

    assert "patient.phone" in result.missing_fields
    assert "patient.phone" not in result.required_missing_fields


def test_source_metadata_is_recorded():
    candidate = {
        "candidate_id": "TEST-27-005",
        "disease": "measles",
        "patient": {
            "county": "Travis",
        },
    }

    result = populate_report_fields(candidate)

    assert result.sources["patient.county"] == "patient.county"


def test_confidence_is_deterministic_for_direct_mapping():
    candidate = {
        "candidate_id": "TEST-27-006",
        "disease": "measles",
        "patient": {
            "county": "Travis",
        },
    }

    result = populate_report_fields(candidate)

    assert result.confidence["patient.county"] == 1.0


def test_nested_missing_source_does_not_invent_value():
    candidate = {
        "candidate_id": "TEST-27-007",
        "disease": "measles",
        "patient": {},
    }

    result = populate_report_fields(candidate)

    assert "patient.city" in result.missing_fields
    assert "patient.city" not in result.fields