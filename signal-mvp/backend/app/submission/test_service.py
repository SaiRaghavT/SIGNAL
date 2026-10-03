from types import SimpleNamespace

from backend.app.submission.service import submit_ecr


def make_ecr(status="REPORT"):
    return SimpleNamespace(ecr_id="ECR-1", status=status)


def make_validation(valid=True):
    return SimpleNamespace(valid=valid, errors=[], warnings=[], completion_required=[])


def test_submission_requires_attestation():
    result = submit_ecr(make_ecr(), make_validation())

    assert result.status == "BLOCKED"
    assert result.submission_id is None
    assert "attestation" in result.errors[0].lower()


def test_submission_requires_complete_validation():
    result = submit_ecr(make_ecr(), make_validation(False))

    assert result.status == "BLOCKED"
    assert result.submission_id is None


def test_malformed_ecr_is_rejected():
    validation = SimpleNamespace(valid=False, errors=["ECR ID is missing."], warnings=[], completion_required=[])
    result = submit_ecr(make_ecr(), validation)

    assert result.status == "REJECTED"
    assert result.errors == ["ECR ID is missing."]


def test_attested_report_can_be_submitted():
    result = submit_ecr(make_ecr(), make_validation(), attested=True)

    assert result.status == "SUBMITTED"
    assert result.submission_id == "SUB-ECR-1"


def test_hold_cannot_be_submitted_even_if_attested():
    result = submit_ecr(make_ecr("HOLD"), make_validation(), attested=True)

    assert result.status == "BLOCKED"
