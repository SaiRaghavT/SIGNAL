from types import SimpleNamespace

from backend.app.agents.retry_resubmission.schemas import RetryResubmissionRequest
from backend.app.agents.retry_resubmission.service import RetryResubmissionService
from backend.app.models.case import Case
from backend.app.models.submissions import Submission
from backend.app.models.workflow_records import CaseWorkflowRecord, Report, SubmissionAttempt


class FakeQuery:
    def __init__(self, rows):
        self.rows = list(rows)

    def filter(self, *expressions):
        for expression in expressions:
            column = expression.left.key
            operator = expression.operator.__name__
            if operator == "is_not":
                expected = None
                self.rows = [
                    row for row in self.rows
                    if getattr(row, column) is not expected
                ]
            else:
                expected = getattr(expression.right, "value", None)
                self.rows = [
                    row for row in self.rows
                    if getattr(row, column) == expected
                ]
        return self

    def order_by(self, *expressions):
        return self

    def first(self):
        return self.rows[0] if self.rows else None

    def count(self):
        return len(self.rows)


class FakeSession:
    def __init__(self, records):
        self.records = records

    def query(self, model):
        return FakeQuery(self.records.get(model, []))

    def add(self, record):
        self.records.setdefault(type(record), []).append(record)

    def commit(self):
        pass

    def refresh(self, record):
        pass


def _session(*, report=True):
    case_id = "case-001"
    submission = SimpleNamespace(
        submission_id="SUB-1",
        case_id=case_id,
        ecr_id="ECR-1",
        report_id="REPORT-1" if report else None,
        channel="eCR",
        destination="MOCK_PHA",
        status="FAILED",
        warnings=[],
        errors=["transport failed"],
        ecr_payload={"resourceType": "Bundle"},
    )
    records = {
        Submission: [submission],
        SubmissionAttempt: [],
        Case: [SimpleNamespace(case_id=case_id, submission_mode="BATCH")],
        Report: [
            SimpleNamespace(report_id="REPORT-1", status="GENERATED")
        ] if report else [],
        CaseWorkflowRecord: [
            SimpleNamespace(case_id=case_id, record_type="REVIEW", status="APPROVE"),
            SimpleNamespace(case_id=case_id, record_type="ATTESTATION", status="ATTESTED"),
        ],
    }
    return FakeSession(records), submission


def test_retry_requires_a_persisted_generated_report():
    db, submission = _session(report=False)

    response = RetryResubmissionService().retry(
        RetryResubmissionRequest(submission_id=submission.submission_id),
        db,
    )

    assert response.status == "BLOCKED"
    assert response.new_submission_id is None
    assert response.errors == ["A generated report is required before retrying submission."]
    assert db.records[SubmissionAttempt][0].status == "BLOCKED"


def test_retry_creates_one_resubmission_and_reuses_it_while_active(monkeypatch):
    db, submission = _session()
    monkeypatch.setattr(
        "backend.app.agents.retry_resubmission.service.build_ecr",
        lambda case: SimpleNamespace(ecr_id="ECR-1"),
    )
    monkeypatch.setattr(
        "backend.app.agents.retry_resubmission.service.validate_ecr",
        lambda ecr, smart_fields: SimpleNamespace(valid=True),
    )
    monkeypatch.setattr(
        "backend.app.agents.retry_resubmission.service.smart_fields_for_case",
        lambda case: {},
    )
    monkeypatch.setattr(
        "backend.app.agents.retry_resubmission.service.case_has_current_attestation",
        lambda db, case: True,
    )
    monkeypatch.setattr(
        "backend.app.agents.retry_resubmission.service.submit_ecr",
        lambda ecr, validation, attested: SimpleNamespace(
            status="SUBMITTED",
            errors=[],
            warnings=[],
        ),
    )
    request = RetryResubmissionRequest(
        submission_id=submission.submission_id,
        reason="Corrected report",
    )
    service = RetryResubmissionService()

    first = service.retry(request, db)
    second = service.retry(request, db)

    assert first.status == "RESUBMITTED"
    assert first.new_submission_id is not None
    assert second.new_submission_id == first.new_submission_id
    assert len(db.records[SubmissionAttempt]) == 1
    assert len(db.records[Submission]) == 2
    assert db.records[Submission][1].submission_mode == "BATCH"


def test_retry_requires_approved_review_and_attestation():
    db, submission = _session()
    db.records[CaseWorkflowRecord] = []

    response = RetryResubmissionService().retry(
        RetryResubmissionRequest(submission_id=submission.submission_id),
        db,
    )

    assert response.status == "BLOCKED"
    assert response.errors == ["An approved review is required before retrying submission."]
