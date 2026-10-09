import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from fastapi.testclient import TestClient
from types import SimpleNamespace

from backend.app.admin import router as admin_router
from backend.app.admin.schemas import BatchCreateRequest, QueueRequest
from backend.app.database import get_db
from backend.app.main import app


class EmptyQuery:
    def filter(self, *args):
        return self

    def order_by(self, *args):
        return self

    def first(self):
        return None

    def all(self):
        return []

    def count(self):
        return 0

    def distinct(self):
        return self


class EmptySession:
    def query(self, *args):
        return EmptyQuery()


def test_admin_api_contract_is_registered_in_openapi():
    paths = app.openapi()["paths"]
    expected = {
        "/api/cases/{case_id}/queue",
        "/api/admin/dashboard",
        "/api/demo/reset",
        "/api/admin/queue",
        "/api/admin/queue/{case_id}",
        "/api/admin/cases/{case_id}/dispatch",
        "/api/admin/submissions",
        "/api/admin/submissions/{submission_id}/acknowledge",
        "/api/admin/submissions/{submission_id}/retry",
        "/api/admin/batches",
        "/api/admin/batches/{batch_id}/dispatch",
        "/api/admin/deadlines",
        "/api/admin/audit",
    }
    assert expected <= paths.keys()


@pytest.mark.parametrize("mode", ["IMMEDIATE", "INDIVIDUAL", "BATCH"])
def test_queue_request_accepts_supported_shared_submission_modes(mode):
    request = QueueRequest(actor_id="clinician-1", submission_mode=mode)
    assert request.submission_mode == mode


def test_queue_request_rejects_unknown_submission_mode():
    with pytest.raises(ValidationError):
        QueueRequest(actor_id="clinician-1", submission_mode="DEFERRED")


def test_batch_request_requires_case_ids_and_actor():
    with pytest.raises(ValidationError):
        BatchCreateRequest(case_ids=[], actor_id="admin-1")


def test_batch_payload_keeps_unique_record_id_separate_from_display_label():
    row = SimpleNamespace(
        record_id="ADMIN-WF-BATCH-001",
        status="PENDING",
        payload={"batch_id": "BATCH-TX-MEASLES-001", "destination": "Texas DSHS"},
        created_at="2026-10-08T00:00:00Z",
    )

    payload = admin_router._batch_payload(row)

    assert payload["batch_id"] == "ADMIN-WF-BATCH-001"
    assert payload["display_batch_id"] == "BATCH-TX-MEASLES-001"
    assert payload["destination"] == "Texas DSHS"


def test_batch_without_linked_cases_cannot_be_dispatched():
    batch = SimpleNamespace(
        record_id="ADMIN-WF-BATCH-001",
        record_type="ADMIN_BATCH",
        status="PENDING",
        payload={"batch_id": "BATCH-TX-MEASLES-001"},
    )

    class Query:
        def filter(self, *_args):
            return self

        def first(self):
            return batch

    class Session:
        def query(self, *_args):
            return Query()

    with pytest.raises(HTTPException) as exc_info:
        admin_router.dispatch_batch("ADMIN-WF-BATCH-001", db=Session())

    assert exc_info.value.status_code == 409
    assert "no linked cases" in exc_info.value.detail


def test_empty_admin_queue_and_dashboard_use_empty_persisted_state():
    def override_get_db():
        yield EmptySession()

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app)
        queue = client.get("/api/admin/queue")
        dashboard = client.get("/api/admin/dashboard")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert queue.status_code == 200
    assert queue.json() == {"items": [], "total": 0}
    assert dashboard.status_code == 200
    assert dashboard.json()["ready_for_submission"] == 0
    assert dashboard.json()["pending_batches"] == 0


@pytest.mark.parametrize(
    ("case_fields", "expected"),
    [
        (
            {
                "severity": "HIGH",
                "rule_id": "rule-123",
                "clinical_evidence": {"symptoms": ["fever"]},
                "laboratory_evidence": [{"test": "PCR", "result": "positive"}],
                "ai_evidence": {"confidence": 0.97},
                "report_fields": {"onset_date": "2026-10-01"},
            },
            {
                "severity": "HIGH",
                "rule_id": "rule-123",
                "clinical_evidence": {"symptoms": ["fever"]},
                "laboratory_evidence": [{"test": "PCR", "result": "positive"}],
                "ai_evidence": {"confidence": 0.97},
                "report_fields": {"onset_date": "2026-10-01"},
            },
        ),
        (
            {
                "severity": None,
                "rule_id": None,
                "clinical_evidence": None,
                "laboratory_evidence": None,
                "ai_evidence": None,
                "report_fields": None,
            },
            {
                "severity": None,
                "rule_id": None,
                "clinical_evidence": {},
                "laboratory_evidence": [],
                "ai_evidence": {},
                "report_fields": {},
            },
        ),
    ],
)
def test_admin_case_detail_includes_stored_evidence_and_preserves_existing_fields(
    monkeypatch, case_fields, expected
):
    case = SimpleNamespace(
        case_id="00000000-0000-0000-0000-000000000001",
        **case_fields,
    )
    existing_fields = {"case_id": "case-1", "priority": "HIGH", "submission_mode": "IMMEDIATE"}
    monkeypatch.setattr(admin_router, "_case", lambda db, case_id: case)
    monkeypatch.setattr(admin_router, "_case_payload", lambda db, case: existing_fields)
    monkeypatch.setattr(
        admin_router,
        "_validation",
        lambda case: {
            "valid": True,
            "errors": [],
            "missing_information": [],
            "warnings": [],
        },
    )

    def override_get_db():
        yield EmptySession()

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = TestClient(app).get("/api/admin/queue/case-1")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    payload = response.json()
    assert {key: payload[key] for key in existing_fields} == existing_fields
    assert {key: payload[key] for key in expected} == expected
