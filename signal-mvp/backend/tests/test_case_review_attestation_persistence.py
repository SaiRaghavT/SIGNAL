from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app.agents.attestation_control.schemas import AttestationResponse
from backend.app.database import get_db
from backend.app.case.workflow_api import _validation, queue_case
from backend.app.demo.admin_demo_reporting import apply_admin_demo_reporting_defaults
from backend.app.main import app
from backend.app.models.case import Case
from backend.app.models.workflow_records import CaseWorkflowRecord, Report
from backend.app.admin.schemas import QueueRequest
from fastapi import HTTPException


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

    def with_for_update(self):
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
        self.records = {CaseWorkflowRecord: [], Report: []}

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
    case = SimpleNamespace(
        case_id=case_id,
        status="NEEDS_REVIEW",
        submission_mode=None,
        rule_id="MEASLES-TX",
        disease="measles",
        jurisdiction="TX",
        deadline=None,
    )
    session = FakeSession(case)
    session.records[Report].append(SimpleNamespace(
        report_id="report-1", case_id=str(case_id), status="GENERATED",
        created_at=datetime.now(timezone.utc),
    ))
    monkeypatch.setattr(
        "backend.app.case.workflow_api._validation",
        lambda case, db=None: {"valid": True, "errors": [], "warnings": [], "missing_fields": []},
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
        repeated_review = client.post(
            f"/api/cases/{case_id}/review",
            json={
                "reviewer_id": "clinical-staff@example.org",
                "reviewer_role": "REPORTING_STAFF",
                "decision": "APPROVE",
                "comments": "Reviewed completed reporting package.",
            },
        )
        assert repeated_review.json()["record_id"] == review_response.json()["record_id"]

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
        repeated_attestation = client.post(
            f"/api/cases/{case_id}/attestation",
            json={
                "reviewer_id": "clinical-staff@example.org",
                "reviewer_role": "REPORTING_STAFF",
                "attestation_status": "ATTESTED",
                "comments": "I attest to this completed package.",
            },
        )
        assert repeated_attestation.json()["record_id"] == attestation_response.json()["record_id"]

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

        # Older workflow records may persist APPROVED instead of APPROVE.
        session.records[CaseWorkflowRecord][0].status = "APPROVED"

        queue_response = client.post(
            f"/api/cases/{case_id}/queue",
            json={"actor_id": "clinical-staff@example.org"},
        )
        assert queue_response.status_code == 201
        assert queue_response.json()["queue_status"] == "READY_FOR_SUBMISSION"
        assert queue_response.json()["submission_mode"] == "IMMEDIATE"
        assert case.submission_mode == "IMMEDIATE"

        repeated_handoff = client.post(
            f"/api/cases/{case_id}/queue",
            json={"actor_id": "clinical-staff@example.org"},
        )
        assert repeated_handoff.status_code == 201
        assert repeated_handoff.json()["queue_status"] == "READY_FOR_SUBMISSION"
        assert repeated_handoff.json()["submission_mode"] == "IMMEDIATE"
        assert sum(row.record_type == "ADMIN_QUEUE" for row in session.records[CaseWorkflowRecord]) == 1
        assert sum(row.record_type == "REVIEW" for row in session.records[CaseWorkflowRecord]) == 1
        assert sum(row.record_type == "ATTESTATION" for row in session.records[CaseWorkflowRecord]) == 1
        assert session.records[CaseWorkflowRecord][-1].status == "READY_FOR_SUBMISSION"

        monkeypatch.setattr(
            "backend.app.admin.router._case_payload",
            lambda db, queued_case: {
                "case_id": str(queued_case.case_id),
                "submission_mode": queued_case.submission_mode,
                "queue_status": "READY_FOR_SUBMISSION",
            },
        )
        admin_queue_response = client.get("/api/admin/queue")
        assert admin_queue_response.status_code == 200
        assert admin_queue_response.json() == {
            "items": [{
                "case_id": str(case_id),
                "submission_mode": "IMMEDIATE",
                "queue_status": "READY_FOR_SUBMISSION",
            }],
            "total": 1,
        }

        persisted_types = [row.record_type for row in session.records[CaseWorkflowRecord]]
        assert persisted_types == ["REVIEW", "ATTESTATION", "SUBMISSION_READINESS", "ADMIN_QUEUE"]
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_admin_static_demo_case_can_be_approved_through_api(monkeypatch):
    case = SimpleNamespace(
        case_id=uuid4(),
        candidate_id="ADMIN-DEMO-BATCH-001",
        status="REPORT",
        disease="measles",
        jurisdiction="TX",
        jurisdiction_status="RESOLVED",
        reportability_decision="REPORT",
        reportability_evidence_status="LAB_POSITIVE",
        final_decision="REPORT",
        rule_id="MEASLES-TX",
        patient={"first_name": "Michael", "last_name": "Brown", "patient_id": str(uuid4())},
        facility={"name": "SIGNAL Demo Hospital", "state": "TX"},
        provider={"name": "Dr. Demo Provider"},
        clinical_evidence={"condition": "Measles"},
        laboratory_evidence={"test": "Measles virus RNA PCR", "result": "Positive"},
        ai_evidence={},
        report_fields={"condition": "Measles", "jurisdiction": "TX"},
        warnings=[],
    )

    session = FakeSession(case)
    monkeypatch.setattr("backend.app.case.workflow_api.audit.record_event", lambda *args, **kwargs: None)

    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        response = client.post(
            f"/api/cases/{case.case_id}/review",
            json={
                "reviewer_id": "clinical-staff@example.org",
                "reviewer_role": "REPORTING_STAFF",
                "decision": "APPROVE",
                "comments": "Reviewed the static demo reporting package.",
            },
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 201
    assert response.json()["status"] == "APPROVE"


def test_queue_rejects_incomplete_reporting_package(monkeypatch):
    case_id = uuid4()
    case = SimpleNamespace(
        case_id=case_id,
        submission_mode=None,
        rule_id=None,
        disease="condition requiring review",
        jurisdiction="TX",
        deadline=None,
    )
    session = FakeSession(case)
    session.records[CaseWorkflowRecord].extend([
        SimpleNamespace(case_id=str(case_id), status="APPROVE", record_id="review-1", record_type="REVIEW", actor_id="staff"),
        SimpleNamespace(case_id=str(case_id), status="ATTESTED", record_id="attestation-1", record_type="ATTESTATION", actor_id="staff"),
    ])
    monkeypatch.setattr(
        "backend.app.case.workflow_api._validation",
        lambda *_args, **_kwargs: {"valid": False, "errors": [], "warnings": [], "missing_fields": ["patient.date_of_birth"]},
    )

    with pytest.raises(HTTPException) as caught:
        queue_case(case_id, QueueRequest(actor_id="staff"), session)
    assert caught.value.status_code == 409
    assert caught.value.detail["validation"]["missing_fields"] == ["patient.date_of_birth"]

    assert not any(row.record_type == "ADMIN_QUEUE" for row in session.records[CaseWorkflowRecord])


def test_demo_defaults_do_not_apply_to_non_demo_cases():
    case = SimpleNamespace(
        candidate_id="real-candidate-1",
        disease="measles",
        facility={"name": "Community Hospital"},
        patient={"first_name": "Ari"},
        provider={},
        report_fields={},
        clinical_evidence={},
        warnings=[],
    )

    assert apply_admin_demo_reporting_defaults(case) == []
    assert case.report_fields == {}
    assert case.warnings == []
