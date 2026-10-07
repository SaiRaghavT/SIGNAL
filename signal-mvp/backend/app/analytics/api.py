from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.case import Case
from backend.app.models.deadline_escalation import DeadlineEscalation
from backend.app.models.submissions import Submission

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


def _counts(db: Session, column, count_column) -> dict[str, int]:
    return {
        str(key): count
        for key, count in db.query(column, func.count(count_column)).group_by(column).all()
    }


@router.get("/summary")
def analytics_summary(db: Session = Depends(get_db)) -> dict:
    return {
        "cases": db.query(Case.case_id).count(),
        "submissions": db.query(Submission.submission_id).count(),
        "deadlines": db.query(DeadlineEscalation.escalation_id).count(),
    }


@router.get("/cases")
def analytics_cases(db: Session = Depends(get_db)) -> dict:
    return {
        "by_status": _counts(db, Case.status, Case.case_id),
        "by_disease": _counts(db, Case.disease, Case.case_id),
        "by_jurisdiction": _counts(db, Case.jurisdiction, Case.case_id),
    }


@router.get("/reporting")
def analytics_reporting(db: Session = Depends(get_db)) -> dict:
    return {
        "by_decision": _counts(db, Case.final_decision, Case.case_id),
        "reportable_cases": db.query(Case.case_id).filter(Case.final_decision == "REPORT").count(),
        "needs_review": db.query(Case.case_id).filter(Case.status == "NEEDS_REVIEW").count(),
    }


@router.get("/submissions")
def analytics_submissions(db: Session = Depends(get_db)) -> dict:
    return {
        "by_status": _counts(db, Submission.status, Submission.submission_id),
        "by_destination": _counts(db, Submission.destination, Submission.submission_id),
    }


@router.get("/deadlines")
def analytics_deadlines(db: Session = Depends(get_db)) -> dict:
    return {
        "by_status": _counts(db, DeadlineEscalation.status, DeadlineEscalation.escalation_id),
        "overdue": db.query(DeadlineEscalation.escalation_id).filter(DeadlineEscalation.status == "OVERDUE").count(),
        "upcoming": db.query(DeadlineEscalation.escalation_id).filter(DeadlineEscalation.status == "UPCOMING").count(),
    }\n