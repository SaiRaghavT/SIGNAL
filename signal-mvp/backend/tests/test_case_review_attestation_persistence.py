from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app.agents.attestation_control.schemas import AttestationResponse
from backend.app.database import get_db
from backend.app.main import app
from backend.app.models.case import Case
from backend.app.models.workflow_records import CaseWorkflowRecord


class FakeQuery:
    def __init__(self, session, model):
        self.session = session
        self.model = model
        self.rows = list(session.records.get(model, []))

    def filter(self, *expressions):
        for expression in expressions:
            key = expression.left.key
            operator = expression.operator.__name__
            if operator == "eq":
                expected = getattr(expression.right, "value", expression.right)
                self.rows = [row for row in self.rows if getattr(row, key) == expected]
            elif operator in {"in_op", "not_in_op"}:
                expected = expression.right.value
                matched = lambda row: getattr(row, key) in expected
                self.rows = [row for row in self.rows if matched(row) == (operator == "in_op")]
        return self

    def order_by(self, *expressions):
        return self

    def first(self):
        if self.model is Case:
            return self.session.case
        return self.rows[-1] if self.rows else None

    def all(self):
        if self.model is Case:
            return [self.session.case]
        return self.rows


class FakeSession:
    def __init__(self, case):
        self.case = case
        self.records = {CaseWorkflowRecord: []}

    def query(self, model):
        return FakeQuery(self, model)

    def add(self, record):
        self.records.setdefault(type(record), []).append(record)

    def commit(self):
        pass

    def refresh(self, record):
        record.record_id = record.record_id or str(uuid4())
        record.created_at = record.created_at or datetime.now(timezone.utc)
        record.updated_at = record.updated_at or record.created_at


def test_review_and_attestation_are_persisted_and_used_for_readiness(monkeypatch):
    case_id = uuid4()
    case = SimpleNamespace(case_id=case_id, status="NEEDS_REVIEW", submission_mode="INDIVIDUAL", deadline=None)
    session = FakeSession(case)
    monkeypatch.setattr(
        "backend.app.case.workflow_api._validation",
        lambda case: {"valid": True, "errors": [], "warnings": [], "missing_fields": []},
    )
    monkeypatch.setattr(
        "backend.app.case.workflow_api.AttestationControlService.validate",
        lambda self, request, db: AttestationResponse(
            case_reference=request.case_reference,
            reviewer_id=request.reviewer_id,
            reviewer_role=request.reviewer_role,
            attestation_status=request.attestation_status,
            authorized=True,
            message="Authorized.",
            comments=request.comments,
        ),
    )
    monkeypatch.setattr(
        "backend.app.case.workflow_api.audit.record_event",
        lambda *args, **kwargs: None,
    )

    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        review_response = client.post(
            f"/api/cases/{case_id}/review",
            json={
                "reviewer_id": "clinical-staff@example.org",
                "reviewer_role": "REPORTING_STAFF",
                "decision": "APPROVE",
                "comments": "Reviewed completed reporting package.",
            },
        )
        assert review_response.status_code == 201
        assert review_response.json()["record_type"] == "REVIEW"
        assert review_response.json()["status"] == "APPROVE"

        attestation_response = client.post(
            f"/api/cases/{case_id}/attestation",
            json={
                "reviewer_id": "clinical-staff@example.org",
                "reviewer_role": "REPORTING_STAFF",
                "attestation_status": "ATTESTED",
                "comments": "I attest to this completed package.",
            },
        )
        assert attestation_response.status_code == 200
        assert attestation_response.json()["record_type"] == "ATTESTATION"
        assert attestation_response.json()["status"] == "ATTESTED"

        readiness_response = client.post(
            f"/api/cases/{case_id}/submission-readiness",
            json={
                "actor_id": "clinical-staff@example.org",
                "review_confirmed": False,
                "review_decision": "APPROVE",
                "attestation_confirmed": False,
            },
        )
        assert readiness_response.status_code == 200
        assert readiness_response.json()["ready"] is True
        assert readiness_response.json()["record"]["status"] == "READY"

        queue_response = client.post(
            f"/api/cases/{case_id}/queue",
            json={
                "actor_id": "clinical-staff@example.org",
                "submission_mode": "INDIVIDUAL",
            },
        )
        assert queue_response.status_code == 201
        assert queue_response.json()["queue_status"] == "QUEUED"
        assert queue_response.json()["submission_mode"] == "INDIVIDUAL"
        assert case.submission_mode == "INDIVIDUAL"

        repeated_handoff = client.post(
            f"/api/cases/{case_id}/queue",
            json={"actor_id": "clinical-staff@example.org"},
        )
        assert repeated_handoff.status_code == 201
        assert repeated_handoff.json()["submission_mode"] == "INDIVIDUAL"
        assert sum(row.record_type == "ADMIN_QUEUE" for row in session.records[CaseWorkflowRecord]) == 1

        monkeypatch.setattr(
            "backend.app.admin.router._case_payload",
            lambda db, queued_case: {"case_id": str(queued_case.case_id)},
        )
        admin_queue_response = client.get("/api/admin/queue")
        assert admin_queue_response.status_code == 200
        assert admin_queue_response.json() == {
            "items": [{"case_id": str(case_id)}],
            "total": 1,
        }

        persisted_types = [row.record_type for row in session.records[CaseWorkflowRecord]]
        assert persisted_types == ["REVIEW", "ATTESTATION", "SUBMISSION_READINESS", "ADMIN_QUEUE"]
    finally:
        app.dependency_overrides.pop(get_db, None)
