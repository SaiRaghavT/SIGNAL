from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.app.models.case import Case
from backend.app.models.deadline_escalation import DeadlineEscalation
from backend.app.models.follow_up import FollowUp
from backend.app.models.submissions import Submission

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
