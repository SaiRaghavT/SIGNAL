from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from backend.app.admin import router as admin_router
from backend.app.admin.schemas import QueueRequest
from backend.app.case import workflow_api
from backend.app.case.workflow_api import AttestationBody, ReviewRequest
from backend.app.models.case import Case
from backend.app.models.workflow_records import CaseWorkflowRecord


class FakeQuery:
    def __init__(self, session, model):
        self.session = session
        self.model = model

    def filter(self, *_expressions):
        return self

    def order_by(self, *_expressions):
        return self

    def with_for_update(self):
        return self

    def first(self):
        if self.model is Case:
            return self.session.case
        rows = self.session.records.get(self.model, [])
        return rows[-1] if rows else None


class FakeSession:
    def __init__(self, case):
        self.case = case
        self.records = {CaseWorkflowRecord: []}

    def query(self, model):
        return FakeQuery(self, model)

    def add(self, row):
        self.records.setdefault(type(row), []).append(row)

    def commit(self):
        pass

    def refresh(self, row):
        row.record_id = row.record_id or str(uuid4())
        row.created_at = row.created_at or datetime.now(timezone.utc)
        row.updated_at = row.updated_at or row.created_at


def synthetic_measles_case():
    return SimpleNamespace(
        case_id=uuid4(),
        patient={"provenance": {"source": "synthea"}},
        facility={"source": "synthea"},
        disease="http://snomed.info/sct|14189004",
        jurisdiction="TX",
        jurisdiction_status="RESOLVED",
        rule_id="NO_RULE_AVAILABLE",
        submission_mode=None,
        final_decision="NEEDS_REVIEW",
        status="NEEDS_REVIEW",
    )


def test_synthetic_measles_demo_queue_is_persisted_and_blocked_from_dispatch(monkeypatch):
    monkeypatch.setattr(workflow_api.settings, "demo_queue_enabled", True)
    monkeypatch.setattr(workflow_api.audit, "record_event", lambda *_args, **_kwargs: None)
    case = synthetic_measles_case()
    session = FakeSession(case)

    result = workflow_api.queue_case(
        case.case_id,
        QueueRequest(
            actor_id="clinical-staff@example.org",
            demo_submission=True,
            demo_review_confirmed=True,
        ),
        session,
    )

    records = session.records[CaseWorkflowRecord]
    assert result["queue_status"] == "READY_FOR_SUBMISSION"
    assert result["submission_mode"] == "IMMEDIATE"
    assert result["demo_submission"] is True
    assert [row.record_type for row in records] == ["REVIEW", "ATTESTATION", "ADMIN_QUEUE"]
    assert all(row.payload["demo_submission"] is True for row in records)
    assert case.final_decision == "NEEDS_REVIEW"
    assert case.status == "NEEDS_REVIEW"

    with pytest.raises(HTTPException) as error:
        admin_router._eligible_for_dispatch(session, case)
    assert error.value.status_code == 409
    assert "cannot be dispatched externally" in error.value.detail


def test_submission_readiness_reflects_persisted_admin_queue_handoff(monkeypatch):
    monkeypatch.setattr(workflow_api.settings, "demo_queue_enabled", True)
    monkeypatch.setattr(workflow_api.audit, "record_event", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        workflow_api,
        "_submission_readiness_response",
        lambda _case, ready, row: {
            "ready": ready,
            "record": workflow_api._workflow_record_data(row),
        },
    )
    case = synthetic_measles_case()
    session = FakeSession(case)

    workflow_api.queue_case(
        case.case_id,
        QueueRequest(
            actor_id="clinical-staff@example.org",
            demo_submission=True,
            demo_review_confirmed=True,
        ),
        session,
    )

    response = workflow_api.get_submission_readiness(case.case_id, session)

    assert response["ready"] is True
    assert response["record"]["record_type"] == "ADMIN_QUEUE"
    assert response["record"]["status"] == "READY_FOR_SUBMISSION"
    assert response["record"]["payload"]["demo_submission"] is True


def test_demo_queue_requires_explicit_review_confirmation(monkeypatch):
    monkeypatch.setattr(workflow_api.settings, "demo_queue_enabled", True)
    case = synthetic_measles_case()
    session = FakeSession(case)

    with pytest.raises(HTTPException) as error:
        workflow_api.queue_case(
            case.case_id,
            QueueRequest(actor_id="clinical-staff@example.org", demo_submission=True),
            session,
        )

    assert error.value.status_code == 409
    assert session.records[CaseWorkflowRecord] == []


def test_synthetic_demo_review_and_attestation_are_persisted_without_changing_clinical_decision(monkeypatch):
    monkeypatch.setattr(workflow_api.settings, "demo_queue_enabled", True)
    monkeypatch.setattr(workflow_api.audit, "record_event", lambda *_args, **_kwargs: None)
    case = synthetic_measles_case()
    session = FakeSession(case)

    review = workflow_api.create_review(
        case.case_id,
        ReviewRequest(
            reviewer_id="clinical-staff@example.org",
            reviewer_role="REPORTING_STAFF",
            decision="APPROVE",
            review_confirmed=True,
            demo_simulation=True,
        ),
        session,
    )
    attestation = workflow_api.create_attestation(
        case.case_id,
        AttestationBody(
            reviewer_id="clinical-staff@example.org",
            reviewer_role="REPORTING_STAFF",
            attestation_status="ATTESTED",
            demo_simulation=True,
        ),
        session,
    )

    assert review.status == "APPROVE"
    assert review.payload["demo_submission"] is True
    assert attestation.status == "ATTESTED"
    assert attestation.payload["demo_submission"] is True
    assert case.final_decision == "NEEDS_REVIEW"
    assert case.status == "NEEDS_REVIEW"


def test_admin_demo_authorization_saves_simulation_without_external_submission(monkeypatch):
    case = synthetic_measles_case()
    session = FakeSession(case)
    records = {
        "ADMIN_QUEUE": SimpleNamespace(
            status="READY_FOR_SUBMISSION",
            payload={"demo_submission": True},
        ),
        "REVIEW": SimpleNamespace(
            status="APPROVE",
            payload={"demo_submission": True},
        ),
        "ATTESTATION": SimpleNamespace(
            status="ATTESTED",
            payload={"demo_submission": True},
        ),
        "ADMIN_DEMO_SUBMISSION": None,
    }
    monkeypatch.setattr(admin_router.settings, "demo_queue_enabled", True)
    monkeypatch.setattr(admin_router, "_case", lambda *_args, **_kwargs: case)
    monkeypatch.setattr(admin_router, "_latest", lambda _db, _case_id, kind: records[kind])
    monkeypatch.setattr(admin_router, "_event", lambda *_args, **_kwargs: None)

    result = admin_router.admin_demo_dispatch(str(case.case_id), "admin@example.org", session)

    assert result["status"] == "SIMULATED"
    assert result["demo_submission"] is True
    assert result["externally_dispatched"] is False
    saved = session.records[CaseWorkflowRecord][-1]
    assert saved.record_type == "ADMIN_DEMO_SUBMISSION"
    assert saved.payload["destination"] == "DEMO_SIMULATION"
    assert saved.payload["externally_dispatched"] is False
    assert records["ADMIN_QUEUE"].status == "DISPATCHED"


def test_admin_local_simulation_accepts_any_queued_case_when_enabled(monkeypatch):
    monkeypatch.setattr(admin_router.settings, "demo_queue_enabled", True)
    case = synthetic_measles_case()
    session = FakeSession(case)
    records = {
        "ADMIN_QUEUE": SimpleNamespace(status="READY_FOR_SUBMISSION", payload={}),
        "ADMIN_DEMO_SUBMISSION": None,
    }
    monkeypatch.setattr(admin_router, "_case", lambda *_args, **_kwargs: case)
    monkeypatch.setattr(admin_router, "_latest", lambda _db, _case_id, kind: records[kind])
    monkeypatch.setattr(admin_router, "_event", lambda *_args, **_kwargs: None)

    result = admin_router.admin_demo_dispatch(str(case.case_id), "admin@example.org", session)

    assert result["status"] == "SIMULATED"
    assert result["externally_dispatched"] is False
    saved = session.records[CaseWorkflowRecord][-1]
    assert saved.record_type == "ADMIN_DEMO_SUBMISSION"
    assert "No report was sent" in saved.payload["notice"]
    assert records["ADMIN_QUEUE"].status == "DISPATCHED"
    records["ADMIN_DEMO_SUBMISSION"] = saved
    repeated = admin_router.admin_demo_dispatch(str(case.case_id), "admin@example.org", session)
    assert repeated["record_id"] == saved.record_id
    assert len(session.records[CaseWorkflowRecord]) == 1
