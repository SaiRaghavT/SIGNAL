from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from backend.app.models.case import Case
from backend.app.models.deadline_escalation import DeadlineEscalation
from backend.app.models.follow_up import FollowUp
from backend.app.models.submissions import Submission
from backend.app.models.audit_event import AuditEvent
from backend.app.models.condition import Condition

from .schemas import DashboardSummaryResponse


def get_dashboard_summary(db: Session) -> DashboardSummaryResponse:
    """Aggregate dashboard counts from persisted records only."""

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
    follow_up_cases = db.query(FollowUp.case_id).distinct().count()
    upcoming_deadlines = (
        db.query(DeadlineEscalation.escalation_id)
        .filter(DeadlineEscalation.status == "UPCOMING")
        .count()
    )

    return DashboardSummaryResponse(
        cases=cases,
        reportable_cases=reportable_cases,
        needs_review=needs_review,
        submitted_cases=submitted_cases,
        follow_up_cases=follow_up_cases,
        upcoming_deadlines=upcoming_deadlines,
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
    return {
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
        "quality": {
            "cases_needing_review": required_review,
            "case_count": db.query(Case.case_id).count(),
        },
    }
