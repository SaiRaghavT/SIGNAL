from types import SimpleNamespace

from backend.app.schemas.validation import validate_ecr


def make_ecr(**overrides):
    data = {
        "ecr_id": "ECR-001",
        "case_id": "CASE-001",
        "candidate_id": "CAND-001",
        "jurisdiction": "TX",
        "disease": "measles",
        "patient": {
            "date_of_birth": "1985-05-05",
        },
        "facility": {
            "name": "Test Hospital",
        },
        "provider": {
            "name": "Dr. Test",
            "phone": "555-0100",
            "address": "Test address",
        },
        "clinical_evidence": {
            "symptoms": ["fever", "rash"],
        },
        "laboratory_evidence": [
            {
                "result": "POSITIVE",
            }
        ],
        "reportability_decision": "REPORT",
        "reportability_evidence_status": "LAB_POSITIVE",
        "status": "REPORT",
    }

    data.update(overrides)
    return SimpleNamespace(**data)


def test_valid_ecr():
    ecr = make_ecr()

    result = validate_ecr(ecr)

    assert result.valid is True
    assert result.errors == []


def test_missing_patient_dob_requires_completion():
    ecr = make_ecr(
        patient={}
    )

    result = validate_ecr(ecr)

    assert result.valid is False
    assert "Patient date of birth is missing." in result.completion_required


def test_missing_provider_requires_completion():
    ecr = make_ecr(
        provider={}
    )

    result = validate_ecr(ecr)

    assert result.valid is False
    assert "Provider information requires completion: name, phone, address." in result.completion_required


def test_missing_required_form_fields_require_completion():
    ecr = make_ecr()

    smart_fields = SimpleNamespace(
        missing_fields=[
            "patient.date_of_birth",
            "patient.sex",
            "laboratory.igm",
        ],
        required_missing_fields=[
            "patient.date_of_birth",
            "patient.sex",
            "laboratory.igm",
        ],
    )

    result = validate_ecr(ecr, smart_fields)

    assert result.valid is False
    assert result.completion_required == ["patient.date_of_birth", "patient.sex", "laboratory.igm"]


def test_missing_optional_form_fields_are_warnings():
    ecr = make_ecr()

    smart_fields = SimpleNamespace(
        missing_fields=[
            "patient.phone",
            "laboratory.pcr",
        ],
        required_missing_fields=[],
    )

    result = validate_ecr(ecr, smart_fields)

    assert result.valid is True
    assert "Optional report field is missing: patient.phone" in result.warnings
    assert "Optional report field is missing: laboratory.pcr" in result.warnings


def test_hold_status_generates_warning():
    ecr = make_ecr(
        status="HOLD"
    )

    result = validate_ecr(ecr)

    assert result.valid is True
    assert "ECR status is HOLD; submission should not proceed." in result.warnings


def test_needs_review_status_generates_warning():
    ecr = make_ecr(
        status="NEEDS_REVIEW"
    )

    result = validate_ecr(ecr)

    assert result.valid is True
    assert "ECR status is NEEDS_REVIEW; submission should not proceed." in result.warnings


def test_missing_ecr_identity_is_error():
    ecr = make_ecr(
        ecr_id="",
        case_id="",
        candidate_id="",
    )

    result = validate_ecr(ecr)

    assert result.valid is False
    assert "ECR ID is missing." in result.errors
    assert "Case ID is missing." in result.errors
    assert "Candidate ID is missing." in result.errors
