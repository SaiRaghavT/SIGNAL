from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app.database import get_db
from backend.app.main import app
from backend.app.models.case import Case
from backend.app.models.workflow_records import CaseWorkflowRecord


def make_case():
    now = datetime.now(timezone.utc)

    return SimpleNamespace(
        case_id=uuid4(),
        disease="measles",
        jurisdiction="TX",
        created_at=now,
        updated_at=now,
    )


class FakeQuery:
    def __init__(self, rows):
        self.rows = list(rows)

    def filter(self, *expressions):
        for expression in expressions:
            column = expression.left.key
            expected = expression.right.value
            self.rows = [
                row for row in self.rows
                if str(getattr(row, column)) == str(expected)
            ]
        return self

    def order_by(self, *args):
        return self

    def first(self):
        return self.rows[0] if self.rows else None


class FakeSession:
    def __init__(self, case, records=None):
        self.case = case
        self.records = records or []
        self.added = []

    def query(self, model):
        if model is Case:
            return FakeQuery([self.case])
        if model is CaseWorkflowRecord:
            return FakeQuery(self.records)
        return FakeQuery([])

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        pass

    def refresh(self, obj):
        obj.record_id = str(uuid4())
        now = datetime.now(timezone.utc)
        obj.created_at = now
        obj.updated_at = now


def make_record(case, record_type, status):
    now = datetime.now(timezone.utc)

    return SimpleNamespace(
        record_id=str(uuid4()),
        case_id=str(case.case_id),
        record_type=record_type,
        status=status,
        actor_id="test-user",
        payload={},
        created_at=now,
        updated_at=now,
    )


def client_for(case, records=None):
    session = FakeSession(case, records)

    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app), session


def test_reporting_queue_requires_valid_case(monkeypatch):
    case = make_case()

    monkeypatch.setattr(
        "backend.app.case.workflow_api._validation",
        lambda case: {"valid": False, "errors": [], "warnings": [], "missing_fields": []},
    )

    client, _ = client_for(case)

    try:
        response = client.post(
            f"/api/cases/{case.case_id}/reporting-queue",
            json={"actor_id": "clinical-user"},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 409


def test_reporting_queue_requires_approved_review(monkeypatch):
    case = make_case()

    monkeypatch.setattr(
        "backend.app.case.workflow_api._validation",
        lambda case: {"valid": True},
    )

    validation = make_record(case, "VALIDATION", "VALID")
    client, _ = client_for(case, [validation])

    try:
        response = client.post(
            f"/api/cases/{case.case_id}/reporting-queue",
            json={"actor_id": "clinical-user"},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 409
    assert "approved review" in response.json()["detail"]


def test_reporting_queue_requires_attestation(monkeypatch):
    case = make_case()

    monkeypatch.setattr(
        "backend.app.case.workflow_api._validation",
        lambda case: {"valid": True},
    )

    validation = make_record(case, "VALIDATION", "VALID")
    review = make_record(case, "REVIEW", "APPROVE")

    client, _ = client_for(case, [validation, review])

    try:
        response = client.post(
            f"/api/cases/{case.case_id}/reporting-queue",
            json={"actor_id": "clinical-user"},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 409
    assert "attestation" in response.json()["detail"]


def test_reporting_queue_accepts_valid_case(monkeypatch):
    case = make_case()

    monkeypatch.setattr(
        "backend.app.case.workflow_api._validation",
        lambda case: {"valid": True},
    )

    review = make_record(case, "REVIEW", "APPROVE")
    attestation = make_record(case, "ATTESTATION", "ATTESTED")

    client, session = client_for(case, [review, attestation])

    try:
        response = client.post(
            f"/api/cases/{case.case_id}/reporting-queue",
            json={
                "actor_id": "clinical-user",
                "comments": "Ready for administrator verification.",
            },
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 201

    body = response.json()

    assert body["record_type"] == "REPORTING_QUEUE"
    assert body["status"] == "QUEUED"
    assert body["actor_id"] == "clinical-user"
    assert body["payload"]["disease"] == "measles"
    assert body["payload"]["jurisdiction"] == "TX"

    assert any(
        record.record_type == "REPORTING_QUEUE"
        and record.status == "QUEUED"
        for record in session.added
    )