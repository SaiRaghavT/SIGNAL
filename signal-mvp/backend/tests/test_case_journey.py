from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from backend.app.models.audit_event import AuditEvent
from backend.app.models.case import Case
from backend.app.models.deadline_escalation import DeadlineEscalation
from backend.app.models.follow_up import FollowUp
from backend.app.models.submissions import Submission
from backend.app.models.workflow_records import Report
from backend.app.workflow.router import read_case_journey
from backend.app.workflow.service import STAGE_ORDER


class FakeQuery:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *args):
        return self

    def order_by(self, *args):
        return self

    def first(self):
        return self.rows[0] if self.rows else None

    def all(self):
        return list(self.rows)


class FakeSession:
    def __init__(self, records):
        self.records = records

    def query(self, model):
        return FakeQuery(self.records.get(model, []))


def make_case(case_id=None, candidate_id="candidate-123"):
    now = datetime(2026, 10, 1, tzinfo=timezone.utc)
    return SimpleNamespace(
        case_id=case_id or uuid4(),
        candidate_id=candidate_id,
        patient={"id": "patient-1"},
        facility={},
        provider={},
        disease="measles",
        clinical_evidence={},
        laboratory_evidence=[],
        ai_evidence={},
        jurisdiction="TX",
        jurisdiction_status="RESOLVED",
        reportability_decision="REPORT",
        reportability_evidence_status="SUFFICIENT",
        status="REPORT",
        final_decision="REPORT",
        rule_id="TX-MEASLES",
        warnings=[],
        created_at=now,
        updated_at=now,
    )


def journey_for(case, records=None):
    return read_case_journey(
        case_id=case.case_id,
        db=FakeSession({Case: [case], **(records or {})}),
    )


def stage(response, name):
    return next(item for item in response.journey if item.stage == name)


def test_case_without_submission_or_followup_has_eleven_ordered_stages():
    case = make_case()
    result = journey_for(case)

    assert len(result.journey) == 11
    assert [item.stage for item in result.journey] == list(STAGE_ORDER)
    assert result.current_stage == "CASE"
    assert stage(result, "DATA_INGESTION").available is False
    assert stage(result, "DETECTION").available is False
    assert "candidate_id" in stage(result, "CANDIDATE").data
    assert "history" in " ".join(stage(result, "CANDIDATE").limitations)
    validation = stage(result, "VALIDATION")
    assert validation.available is True
    assert validation.status == "NEEDS_COMPLETION"
    assert validation.data["completion_required"]


def test_unknown_case_returns_404():
    with pytest.raises(HTTPException) as exc:
        read_case_journey(uuid4(), FakeSession({Case: []}))
    assert exc.value.status_code == 404


def test_submission_data_is_from_persisted_submission_record():
    case = make_case()
    submission = SimpleNamespace(
        submission_id="SUB-1",
        ecr_id="ECR-1",
        destination="MOCK_PHA",
        status="SUBMITTED",
        errors=[],
        warnings=["Simulated"],
        created_at=case.created_at,
        updated_at=case.updated_at,
    )
    result = journey_for(case, {Submission: [submission]})

    submission_stage = stage(result, "SUBMISSION")
    assert result.current_stage == "SUBMISSION"
    assert submission_stage.available is True
    assert submission_stage.data["submissions"][0]["submission_id"] == "SUB-1"
    assert any("simulated" in item.lower() for item in submission_stage.limitations)


def test_followup_data_is_from_persisted_followup_record():
    case = make_case()
    follow_up = SimpleNamespace(
        followup_id="FOLLOWUP-1",
        action="REQUEST_INFORMATION",
        status="FOLLOWUP_PENDING",
        notes="Need additional details",
        created_at=case.created_at,
        updated_at=case.updated_at,
    )
    result = journey_for(case, {FollowUp: [follow_up]})

    followup_stage = stage(result, "PHA_FOLLOW_UP")
    assert result.current_stage == "PHA_FOLLOW_UP"
    assert followup_stage.available is True
    assert followup_stage.data["follow_ups"][0]["action"] == "REQUEST_INFORMATION"


def test_historical_reporting_audit_does_not_mark_current_reporting_complete():
    case = make_case()
    audit = SimpleNamespace(
        event_type="CASE_MANUAL_REPORT_PREPARED",
        entity_type="CASE",
        entity_id=str(case.case_id),
        actor_type="SYSTEM",
        actor_id="SIGNAL",
        source_agent="Agent-31",
        status="SUCCESS",
        description="Prepared",
        new_value={"status": "READY_FOR_RENDERING"},
        created_at=case.created_at,
        event_timestamp=case.created_at,
    )
    result = journey_for(case, {AuditEvent: [audit]})
    report_stage = stage(result, "REPORTING")

    assert report_stage.available is False
    assert report_stage.status == "PENDING"
    assert report_stage.agent is None
    assert result.supporting_audit_events[0]["event_type"] == "CASE_MANUAL_REPORT_PREPARED"


def test_current_report_record_marks_reporting_complete():
    case = make_case()
    report = SimpleNamespace(
        report_id="REPORT-1",
        form_id="TX-MEASLES",
        form_version="1",
        render_id="render-1",
        report_type="TEXAS_MEASLES",
        status="GENERATED",
        created_at=case.created_at,
    )
    result = journey_for(case, {Report: [report]})
    report_stage = stage(result, "REPORTING")

    assert report_stage.available is True
    assert report_stage.status == "COMPLETED"
    assert report_stage.entity_reference == "REPORT-1"
    assert report_stage.data["reports"][0]["render_id"] == "render-1"


def test_detection_stage_is_unavailable_without_rerunning_detection():
    result = journey_for(make_case())
    detection = stage(result, "DETECTION")

    assert detection.available is False
    assert detection.status is None
    assert detection.occurred_at is None
