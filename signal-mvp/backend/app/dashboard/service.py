from datetime import datetime, timedelta

from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.orm import Session

from backend.app.models.candidate import Candidate
from backend.app.models.case import Case
from backend.app.models.deadline_escalation import DeadlineEscalation
from backend.app.models.submissions import Submission
from backend.app.models.audit_event import AuditEvent
from backend.app.models.condition import Condition
from backend.app.models.patient import Patient

from .schemas import DashboardSummaryResponse


def get_dashboard_summary(db: Session) -> DashboardSummaryResponse:
    """Aggregate dashboard counts across all patients, conditions, and cases."""

    cases = db.query(Case.case_id).count()
    reportable_cases = (
        db.query(Case.case_id)
        .filter(Case.final_decision == "REPORT")
        .count()
    )

    # The existing case assembler persists NEEDS_REVIEW as final_decision/status
    # when review is required. Include the persisted decision fields as well so
    # cases with a review decision are counted even if another field differs.
    needs_review = (
        db.query(Case.case_id)
        .filter(
            or_(
                Case.status == "NEEDS_REVIEW",
                Case.final_decision == "NEEDS_REVIEW",
                Case.reportability_decision == "NEEDS_REVIEW",
                Case.jurisdiction_status == "NEEDS_REVIEW",
            )
        )
        .count()
    )

    submitted_cases = db.query(Submission.case_id).distinct().count()
    upcoming_deadlines = (
        db.query(DeadlineEscalation.escalation_id)
        .filter(DeadlineEscalation.status == "UPCOMING")
        .count()
    )

    # Dashboard totals use persisted workflow deadlines. Do not build the
    # complete patient worklist here: that recalculates a deadline for every
    # patient and is unnecessary for these aggregate counts.
    patient_count = db.query(Patient.patient_id).count()
    local_now = datetime.now().astimezone()
    start_of_today = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    start_of_tomorrow = start_of_today + timedelta(days=1)
    patients_due_today = {
        row[0]
        for row in (
            db.query(Candidate.patient_id)
            .filter(
                Candidate.deadline >= start_of_today,
                Candidate.deadline < start_of_tomorrow,
            )
            .all()
        )
    }
    patients_due_today.update(
        row[0]
        for row in (
            db.query(Candidate.patient_id)
            .join(Case, Case.candidate_id == Candidate.candidate_id)
            .filter(
                Case.deadline >= start_of_today,
                Case.deadline < start_of_tomorrow,
            )
            .all()
        )
    )

    reported_case_ids = (
        db.query(Submission.case_id.label("case_id"))
        .filter(Submission.status.in_(("SUBMITTED", "ACKNOWLEDGED")))
        .distinct()
        .subquery()
    )
    reported_cases = (
        db.query(Case.case_id)
        .join(reported_case_ids, cast(Case.case_id, String) == reported_case_ids.c.case_id)
        .distinct()
        .count()
    )

    # The case workflow has no separate ACTIVE enum: its open action states are
    # NEEDS_REVIEW and REPORT. Exclude cases with an actual submitted/acknowledged
    # record; HOLD is not an open reporting action.
    active_cases = (
        db.query(Case.case_id)
        .filter(
            Case.status.in_(("NEEDS_REVIEW", "REPORT")),
            ~cast(Case.case_id, String).in_(select(reported_case_ids.c.case_id)),
        )
        .count()
    )

    return DashboardSummaryResponse(
        cases=cases,
        reportable_cases=reportable_cases,
        needs_review=needs_review,
        submitted_cases=submitted_cases,
        upcoming_deadlines=upcoming_deadlines,
        total_patients=patient_count,
        active_cases=active_cases,
        patients_due_today=len(patients_due_today),
        reported_cases=reported_cases,
    )


def get_dashboard_activity(db: Session) -> dict:
    events = db.query(AuditEvent).order_by(AuditEvent.event_timestamp.desc()).limit(20).all()
    return {
        "items": [
            {
                "event_id": event.audit_id,
                "event_type": event.event_type,
                "entity_type": event.entity_type,
                "entity_id": event.entity_id,
                "status": event.status,
                "timestamp": event.event_timestamp,
                "description": event.description,
            }
            for event in events
        ]
    }


def get_dashboard_deadlines(db: Session) -> dict:
    deadlines = (
        db.query(DeadlineEscalation)
        .order_by(DeadlineEscalation.deadline.asc())
        .limit(50)
        .all()
    )
    counts_by_status = (
        db.query(DeadlineEscalation.status, func.count(DeadlineEscalation.escalation_id))
        .group_by(DeadlineEscalation.status)
        .all()
    )
    return {
        "by_status": {str(status): count for status, count in counts_by_status},
        "items": [
            {
                "case_id": item.case_id,
                "deadline": item.deadline,
                "status": item.status,
                "minutes_remaining": item.minutes_remaining,
                "message": item.message,
                "jurisdiction": item.jurisdiction,
                "rule_id": item.rule_id,
            }
            for item in deadlines
        ]
    }


def get_reporting_status(db: Session) -> dict:
    cases_by_status = (
        db.query(Case.status, func.count(Case.case_id))
        .group_by(Case.status)
        .all()
    )
    submissions_by_status = (
        db.query(Submission.status, func.count(Submission.submission_id))
        .group_by(Submission.status)
        .all()
    )
    jurisdictions = (
        db.query(Case.jurisdiction, func.count(Case.case_id))
        .filter(Case.jurisdiction.isnot(None))
        .group_by(Case.jurisdiction)
        .all()
    )
    case_conditions = (
        db.query(Case.disease, func.count(Case.case_id))
        .filter(Case.disease.isnot(None))
        .group_by(Case.disease)
        .order_by(func.count(Case.case_id).desc())
        .limit(20)
        .all()
    )
    conditions = (
        db.query(Condition.condition_display, func.count(Condition.condition_id))
        .filter(Condition.condition_display.isnot(None))
        .group_by(Condition.condition_display)
        .order_by(func.count(Condition.condition_id).desc())
        .limit(20)
        .all()
    )
    required_review = db.query(Case.case_id).filter(Case.status == "NEEDS_REVIEW").count()
    return {
        "cases": {str(name): count for name, count in cases_by_status},
        "submissions": {str(name): count for name, count in submissions_by_status},
        "jurisdictions": {str(name): count for name, count in jurisdictions},
        "conditions": {str(name): count for name, count in conditions},
        "case_conditions": {str(name): count for name, count in case_conditions},
        "quality": {
            "cases_needing_review": required_review,
            "case_count": db.query(Case.case_id).count(),
        },
    }
