from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from backend.app.models.audit_event import AuditEvent
from backend.app.models.candidate import Candidate
from backend.app.models.case import Case
from backend.app.models.deadline_escalation import DeadlineEscalation
from backend.app.models.submissions import Submission
from backend.app.models.workflow_records import CaseWorkflowRecord, Report
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
    "REVIEW",
    "ATTESTATION",
    "REPORTING",
    "SUBMISSION",
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
        "channel": submission.channel,
        "status": submission.status,
        "errors": submission.errors or [],
        "warnings": submission.warnings or [],
        "created_at": submission.created_at,
        "updated_at": submission.updated_at,
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
    reports = (
        db.query(Report)
        .filter(Report.case_id == case_id_text)
        .order_by(Report.created_at.asc())
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
    candidate = db.query(Candidate).filter(Candidate.candidate_id == case.candidate_id).first()

    def workflow_record(record_type: str) -> CaseWorkflowRecord | None:
        return (
            db.query(CaseWorkflowRecord)
            .filter(
                CaseWorkflowRecord.case_id == case_id_text,
                CaseWorkflowRecord.record_type == record_type,
            )
            .order_by(CaseWorkflowRecord.created_at.desc())
            .first()
        )

    ingestion_events = [
        event for event in audit_events
        if (event.metadata_json or {}).get("workflow_stage") == "DATA_INGESTION"
    ]
    detection_events = [
        event for event in audit_events
        if (event.metadata_json or {}).get("workflow_stage") == "DETECTION"
    ]

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

    validation_stage = _validation_stage(case)
    if validation_stage.status == "READY":
        validation_stage.status = "COMPLETED"
    validation_stage.entity_reference = case_id_text
    review_record = workflow_record("REVIEW")
    attestation_record = workflow_record("ATTESTATION")
    stages = [
        JourneyStage(
            stage="DATA_INGESTION",
            available=bool(ingestion_events),
            status="COMPLETED" if ingestion_events else "NOT_STARTED",
            occurred_at=ingestion_events[-1].event_timestamp if ingestion_events else None,
            entity_reference=case_id_text if ingestion_events else None,
            source=ingestion_events[-1].source_agent if ingestion_events else None,
            data={"events": [_audit_data(event) for event in ingestion_events]},
            limitations=[] if ingestion_events else [
                "Ingestion history is not persisted as a run and is not reliably linked to this case."
            ],
        ),
        JourneyStage(
            stage="DETECTION",
            available=candidate is not None,
            status="COMPLETED" if candidate is not None else "NOT_STARTED",
            occurred_at=candidate.created_at if candidate is not None else None,
            entity_reference=candidate.candidate_id if candidate is not None else None,
            source="Persisted candidate record" if candidate is not None else None,
            data={
                "candidate_id": candidate.candidate_id,
                "patient_id": candidate.patient_id,
                "disease": candidate.disease_id,
                "status": candidate.status,
            } if candidate is not None else {},
            limitations=[
                "Detection status reflects the persisted candidate linked to this case; detection is not rerun when the journey is read."
            ] if candidate is not None else [
                "No persisted candidate is linked to this case."
            ],
        ),
        JourneyStage(
            stage="CANDIDATE",
            available=candidate_available,
            status="COMPLETED" if candidate_available else "NOT_STARTED",
            occurred_at=candidate.created_at if candidate else None,
            entity_reference=case.candidate_id if candidate_available else None,
            data={
                "candidate_id": case.candidate_id,
                "status": candidate.status if candidate else "linked_to_case",
                "confidence": candidate.confidence if candidate else None,
            } if candidate_available else {},
            limitations=[
                "Candidate history is not persisted; the current disposition is shown when available."
            ],
        ),
        JourneyStage(
            stage="REPORTABILITY",
            available=reportability_available,
            status="COMPLETED" if reportability_available else "NOT_STARTED",
            occurred_at=case.updated_at if reportability_available else None,
            entity_reference=case.candidate_id,
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
            status="COMPLETED",
            occurred_at=case.created_at,
            entity_reference=case_id_text,
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
        validation_stage,
        JourneyStage(
            stage="REVIEW",
            available=review_record is not None,
            status=review_record.status if review_record else "PENDING",
            occurred_at=review_record.created_at if review_record else None,
            entity_reference=review_record.record_id if review_record else None,
            source="Persisted human review" if review_record else None,
            data=review_record.payload if review_record else {},
        ),
        JourneyStage(
            stage="ATTESTATION",
            available=attestation_record is not None,
            status=attestation_record.status if attestation_record else "PENDING",
            occurred_at=attestation_record.created_at if attestation_record else None,
            entity_reference=attestation_record.record_id if attestation_record else None,
            source="Persisted human attestation" if attestation_record else None,
            data=attestation_record.payload if attestation_record else {},
        ),
        JourneyStage(
            stage="REPORTING",
            available=bool(reports),
            status="COMPLETED" if reports and reports[-1].status == "GENERATED" else "PENDING",
            occurred_at=reports[-1].created_at if reports else None,
            entity_reference=reports[-1].report_id if reports else None,
            data={"reports": [{
                "report_id": item.report_id,
                "form_id": item.form_id,
                "form_version": item.form_version,
                "render_id": item.render_id,
                "report_type": item.report_type,
                "status": item.status,
                "created_at": item.created_at,
            } for item in reports]},
            limitations=(
                ["Current reporting state comes from persisted report records; audit events remain available separately as historical evidence."]
                if reports
                else ["No current report record exists; historical audit events are retained separately and do not mark reporting complete."]
            ),
        ),
        JourneyStage(
            stage="SUBMISSION",
            available=bool(submissions),
            status="COMPLETED" if submissions and submissions[-1].status in {"SUBMITTED", "ACKNOWLEDGED"} else "CURRENT" if submissions else "PENDING",
            occurred_at=submissions[-1].created_at if submissions else None,
            entity_reference=submissions[-1].submission_id if submissions else None,
            data={"submissions": [_submission_data(item) for item in submissions]},
            limitations=(
                ["A stored submission status does not establish actual public-health delivery."]
                + (["The destination is simulated (MOCK_PHA)."] if any(item.destination == "MOCK_PHA" for item in submissions) else [])
                if submissions
                else []
            ),
        ),
    ]

    # Use only persisted submission records; otherwise the known case is the
    # furthest established workflow stage.
    current_stage = "SUBMISSION" if submissions else "CASE"

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
