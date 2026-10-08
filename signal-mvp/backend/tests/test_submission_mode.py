from dataclasses import dataclass
from types import SimpleNamespace

from backend.app.agents.ecr_submission.schemas import ECRSubmissionRequest
from backend.app.agents.ecr_submission.service import ECRSubmissionService
from backend.app.models.case import Case
from backend.app.models.submissions import Submission
from backend.app.models.workflow_records import CaseWorkflowRecord, Report
from backend.app.submission.models import SubmissionResult


@dataclass
class FakeECR:
    ecr_id: str = "ECR-1"
    status: str = "REPORT"


class FakeQuery:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *args):
        return self

    def order_by(self, *args):
        return self

    def with_for_update(self):
        return self

    def first(self):
        return self.rows[0] if self.rows else None


class FakeSession:
    def __init__(self, case):
        self.case = case
        self.workflow_rows = iter([
            [SimpleNamespace(status="APPROVE")],
            [SimpleNamespace(status="ATTESTED")],
        ])
        self.added = []

    def query(self, model):
        if model is Case:
            return FakeQuery([self.case])
        if model is Submission:
            return FakeQuery([])
        if model is Report:
            return FakeQuery([SimpleNamespace(report_id="REPORT-1")])
        if model is CaseWorkflowRecord:
            return FakeQuery(next(self.workflow_rows))
        raise AssertionError(f"Unexpected query model: {model}")

    def add(self, item):
        self.added.append(item)

    def commit(self):
        pass

    def refresh(self, _item):
        pass


def test_submission_captures_case_mode_and_preserves_submission_behavior(monkeypatch):
    case = SimpleNamespace(case_id="case-1", submission_mode="IMMEDIATE")
    db = FakeSession(case)
    monkeypatch.setattr("backend.app.agents.ecr_submission.service.build_ecr", lambda _case: FakeECR())
    monkeypatch.setattr("backend.app.agents.ecr_submission.service.validate_ecr", lambda *_: SimpleNamespace(valid=True))
    monkeypatch.setattr("backend.app.agents.ecr_submission.service.smart_fields_for_case", lambda _case: {})
    monkeypatch.setattr("backend.app.agents.ecr_submission.service.case_has_current_attestation", lambda *_: True)
    monkeypatch.setattr(
        "backend.app.agents.ecr_submission.service.submit_ecr",
        lambda *_args, **_kwargs: SubmissionResult(
            submission_id="SUB-ECR-1",
            status="SUBMITTED",
            destination="MOCK_PHA",
            errors=[],
            warnings=["Submission is simulated; no real PHA transmission occurred."],
        ),
    )
    monkeypatch.setattr(
        "backend.app.agents.ecr_submission.service.AuditLedgerService.record_event",
        lambda *_args, **_kwargs: None,
    )

    result = ECRSubmissionService().submit(ECRSubmissionRequest(case_id="case-1"), db)

    persisted = db.added[0]
    assert persisted.submission_mode == "IMMEDIATE"
    assert result.submission_mode == "IMMEDIATE"
    assert result.status == "SUBMITTED"
    assert result.destination == "MOCK_PHA"
    assert result.warnings == ["Submission is simulated; no real PHA transmission occurred."]
