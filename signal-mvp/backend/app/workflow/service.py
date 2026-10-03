from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from backend.app.models.audit_event import AuditEvent
from backend.app.models.case import Case
from backend.app.models.deadline_escalation import DeadlineEscalation
from backend.app.models.follow_up import FollowUp
from backend.app.models.submissions import Submission
from backend.app.ecr.builder import build_ecr
from backend.app.schemas.validation import validate_ecr
from backend.app.submission.gates import smart_fields_for_case

from .schemas import CaseJourneyResponse, JourneyStage


STAGE_ORDER = (
    "DATA_INGESTION",
    "DETECTION",
    "CANDIDATE",
    "REPORTABILITY",
    "CASE",
    "VALIDATION",
    "REPORTING",
    "SUBMISSION",
    "PHA_FOLLOW_UP",
)


def _audit_data(event: AuditEvent) -> dict[str, Any]:
    return {
        "event_type": event.event_type,
        "entity_type": event.entity_type,
        "entity_id": event.entity_id,
        "actor_type": event.actor_type,
        "actor_id": event.actor_id,
        "source_agent": event.source_agent,
        "status": event.status,
        "description": event.description,
        "new_value": event.new_value,
        "metadata": getattr(event, "metadata_json", event.__dict__.get("metadata")),
        "event_timestamp": event.event_timestamp,
        "created_at": event.created_at,
    }


def _submission_data(submission: Submission) -> dict[str, Any]:
    return {
        "submission_id": submission.submission_id,
        "ecr_id": submission.ecr_id,
        "destination": submission.destination,
        "status": submission.status,
        "errors": submission.errors or [],
        "warnings": submission.warnings or [],
        "created_at": submission.created_at,
        "updated_at": submission.updated_at,
    }


def _follow_up_data(follow_up: FollowUp) -> dict[str, Any]:
    return {
        "followup_id": follow_up.followup_id,
        "action": follow_up.action,
        "status": follow_up.status,
        "notes": follow_up.notes,
        "created_at": follow_up.created_at,
        "updated_at": follow_up.updated_at,
    }


def _escalation_data(escalation: DeadlineEscalation) -> dict[str, Any]:
    return {
        "escalation_id": escalation.escalation_id,
        "status": escalation.status,
        "escalation_required": escalation.escalation_required,
        "minutes_remaining": escalation.minutes_remaining,
        "deadline": escalation.deadline,
        "message": escalation.message,
        "jurisdiction": escalation.jurisdiction,
        "rule_id": escalation.rule_id,
        "created_at": escalation.created_at,
    }


def _validation_stage(case: Case) -> JourneyStage:
    ecr = build_ecr(case)
    # Validation measures data completeness; case status is represented in
    # the CASE stage and should not create an extra completion error here.
    ecr.status = "REPORT"
    result = validate_ecr(ecr, smart_fields_for_case(case))
    status = "INVALID" if result.errors else "READY" if result.valid else "NEEDS_COMPLETION"
    return JourneyStage(
        stage="VALIDATION",
        available=True,
        status=status,
        source="Persisted case data",
        agent="Agent 33 · ECR Validation",
        data={
            "valid": result.valid,
            "errors": result.errors,
            "completion_required": result.completion_required,
            "warnings": result.warnings,
        },
        limitations=[
            "This is a current validation of persisted case data, not a historical validation record."
        ],
    )


def get_case_journey(db: Session, case_id: UUID) -> CaseJourneyResponse | None:
    case = db.query(Case).filter(Case.case_id == case_id).first()
    if case is None:
        return None

    case_id_text = str(case.case_id)
    submissions = (
        db.query(Submission)
        .filter(Submission.case_id == case_id_text)
        .order_by(Submission.created_at.asc())
        .all()
    )
    follow_ups = (
        db.query(FollowUp)
        .filter(FollowUp.case_id == case_id_text)
        .order_by(FollowUp.created_at.asc())
        .all()
    )
    audit_events = (
        db.query(AuditEvent)
        .filter(
            AuditEvent.entity_type == "CASE",
            AuditEvent.entity_id == case_id_text,
        )
        .order_by(AuditEvent.event_timestamp.asc())
        .all()
    )
    escalations = (
        db.query(DeadlineEscalation)
        .filter(DeadlineEscalation.case_id == case_id_text)
        .order_by(DeadlineEscalation.created_at.asc())
        .all()
    )

    candidate_available = bool(case.candidate_id)
    reportability_available = any(
        value not in (None, "")
        for value in (
            case.reportability_decision,
            case.reportability_evidence_status,
            case.final_decision,
            case.rule_id,
            case.jurisdiction_status,
        )
    )
    reporting_events = [
        event
        for event in audit_events
        if event.event_type == "CASE_MANUAL_REPORT_PREPARED"
    ]

    stages = [
        JourneyStage(
            stage="DATA_INGESTION",
            available=False,
            limitations=[
                "Ingestion history is not persisted as a run and is not reliably linked to this case."
            ],
        ),
        JourneyStage(
            stage="DETECTION",
            available=False,
            limitations=[
                "Detection results are transient; this journey does not rerun detection."
            ],
        ),
        JourneyStage(
            stage="CANDIDATE",
            available=candidate_available,
            data={"candidate_id": case.candidate_id} if candidate_available else {},
            limitations=[
                "Candidate history and disposition are not persisted."
            ],
        ),
        JourneyStage(
            stage="REPORTABILITY",
            available=reportability_available,
            status=case.final_decision or case.reportability_decision,
            occurred_at=case.updated_at if reportability_available else None,
            data={
                "reportability_decision": case.reportability_decision,
                "reportability_evidence_status": case.reportability_evidence_status,
                "final_decision": case.final_decision,
                "rule_id": case.rule_id,
                "jurisdiction_status": case.jurisdiction_status,
                "warnings": case.warnings or [],
                "deadline_escalations": [_escalation_data(item) for item in escalations],
            },
            limitations=[
                "Detailed reportability assessment history and reasoning are not persisted.",
                "The timestamp is the case update time, not a dedicated reportability decision time.",
            ],
        ),
        JourneyStage(
            stage="CASE",
            available=True,
            status=case.status,
            occurred_at=case.created_at,
            data={
                "case_id": case_id_text,
                "candidate_id": case.candidate_id,
                "disease": case.disease,
                "jurisdiction": case.jurisdiction,
                "jurisdiction_status": case.jurisdiction_status,
                "reportability_decision": case.reportability_decision,
                "final_decision": case.final_decision,
                "status": case.status,
                "rule_id": case.rule_id,
                "warnings": case.warnings or [],
                "created_at": case.created_at,
                "updated_at": case.updated_at,
            },
            limitations=[
                "The case record does not contain a foreign-key link to canonical patient or ingestion records."
            ],
        ),
        _validation_stage(case),
        JourneyStage(
            stage="REPORTING",
            available=bool(reporting_events),
            status=reporting_events[-1].status if reporting_events else None,
            occurred_at=reporting_events[-1].event_timestamp if reporting_events else None,
            source=reporting_events[-1].actor_type if reporting_events else None,
            agent=reporting_events[-1].source_agent if reporting_events else None,
            data={"events": [_audit_data(event) for event in reporting_events]},
            limitations=(
                ["The audit event records preparation only; current report fields are available in case detail, while rendered-document metadata is not retained as workflow history."]
                if reporting_events
                else ["No persisted manual-report preparation event was found; generated files alone are not treated as history."]
            ),
        ),
        JourneyStage(
            stage="SUBMISSION",
            available=bool(submissions),
            status=submissions[-1].status if submissions else None,
            occurred_at=submissions[-1].created_at if submissions else None,
            data={"submissions": [_submission_data(item) for item in submissions]},
            limitations=(
                ["A stored submission status does not establish actual public-health delivery."]
                + (["The destination is simulated (MOCK_PHA)."] if any(item.destination == "MOCK_PHA" for item in submissions) else [])
                if submissions
                else []
            ),
        ),
        JourneyStage(
            stage="PHA_FOLLOW_UP",
            available=bool(follow_ups),
            status=follow_ups[-1].status if follow_ups else None,
            occurred_at=follow_ups[-1].created_at if follow_ups else None,
            data={
                "follow_ups": [_follow_up_data(item) for item in follow_ups],
                "submission_statuses": [
                    {
                        "submission_id": item.submission_id,
                        "status": item.status,
                        "acknowledgement_warnings": [
                            warning
                            for warning in (item.warnings or [])
                            if "acknowledgement" in warning.casefold()
                        ],
                    }
                    for item in submissions
                ],
            },
            limitations=[
                "Acknowledgement IDs and PHA case IDs are not persisted.",
                "Acknowledgement and public-health follow-up integrations are simulated.",
            ],
        ),
    ]

    # Conservative current-stage rule: use only persisted follow-up/submission
    # records; otherwise the known case is the furthest established stage.
    current_stage = (
        "PHA_FOLLOW_UP" if follow_ups else "SUBMISSION" if submissions else "CASE"
    )

    return CaseJourneyResponse(
        case_id=case_id_text,
        case_status=case.status,
        disease=case.disease,
        jurisdiction=case.jurisdiction,
        current_stage=current_stage,
        journey=stages,
        supporting_audit_events=[_audit_data(event) for event in audit_events],
        deadline_escalations=[_escalation_data(item) for item in escalations],
    )
