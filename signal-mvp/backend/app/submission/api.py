from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.case import Case
from backend.app.models.submissions import Submission
from backend.app.models.workflow_records import Acknowledgement, SubmissionAttempt
from backend.app.models.audit_event import AuditEvent

router = APIRouter(tags=["Submissions"])


def _submission_payload(db: Session, submission: Submission) -> dict:
    case = db.query(Case).filter(Case.case_id == submission.case_id).first()
    submitted_events = db.query(AuditEvent).filter(
        AuditEvent.entity_type == "CASE",
        AuditEvent.entity_id == submission.case_id,
        AuditEvent.event_type == "SUBMITTED",
    ).order_by(AuditEvent.event_timestamp.desc()).all()
    submitted_event = next((event for event in submitted_events if (event.new_value or {}).get("submission_id") == submission.submission_id), None)
    return {
        "submission_id": submission.submission_id,
        "case_id": submission.case_id,
        "patient": case.patient if case else {},
        "disease": case.disease if case else None,
        "jurisdiction": case.jurisdiction if case else None,

        "submitted_by": submitted_event.actor_id if submitted_event else None,
        "batch_id": (submitted_event.new_value or {}).get("batch_id") if submitted_event else None,
        "pha_case_id": submission.pha_case_id,


        "destination": submission.destination,
        "channel": submission.channel,
        "status": submission.status,
        "created_at": submission.created_at,
        "updated_at": submission.updated_at,
        "acknowledgement_id": submission.acknowledgement_id,
        "errors": submission.errors or [],
        "warnings": submission.warnings or [],
        "report_id": submission.report_id,
        "ecr_id": submission.ecr_id,
    }


@router.get("/api/submissions")
def list_submissions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, max_length=200),
    status: str | None = Query(None, max_length=50),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    db: Session = Depends(get_db),
) -> dict:
    query = db.query(Submission)
    if status:
        query = query.filter(Submission.status == status)
    if search and search.strip():
        pattern = f"%{search.strip()}%"
        query = query.filter(or_(Submission.submission_id.ilike(pattern), Submission.case_id.ilike(pattern), Submission.ecr_id.ilike(pattern)))
    if date_from:
        query = query.filter(Submission.created_at >= datetime.combine(date_from, time.min, tzinfo=timezone.utc))
    if date_to:
        query = query.filter(Submission.created_at < datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=timezone.utc))
    total = query.count()
    records = query.order_by(Submission.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [_submission_payload(db, item) for item in records],
        "page": page,
        "page_size": page_size,
        "total": total,
        "pages": (total + page_size - 1) // page_size,
    }


def _get_submission(db: Session, submission_id: str) -> Submission:
    submission = db.query(Submission).filter(Submission.submission_id == submission_id).first()
    if submission is None:
        raise HTTPException(status_code=404, detail="Submission not found.")
    return submission


@router.get("/api/submissions/{submission_id}")
def get_submission(submission_id: str, db: Session = Depends(get_db)) -> dict:
    return _submission_payload(db, _get_submission(db, submission_id))


@router.get("/api/submissions/{submission_id}/status")
def get_submission_status(submission_id: str, db: Session = Depends(get_db)) -> dict:
    record = _get_submission(db, submission_id)
    return {"submission_id": record.submission_id, "status": record.status, "created_at": record.created_at, "updated_at": record.updated_at}


@router.get("/api/submissions/{submission_id}/ecr")
def get_submission_ecr(submission_id: str, db: Session = Depends(get_db)) -> dict:
    record = _get_submission(db, submission_id)
    if not record.ecr_payload:
        raise HTTPException(status_code=404, detail="ECR payload is unavailable.")
    return record.ecr_payload


@router.get("/api/submissions/{submission_id}/acknowledgement")
def get_submission_acknowledgement(submission_id: str, db: Session = Depends(get_db)) -> dict:
    _get_submission(db, submission_id)
    acknowledgement = db.query(Acknowledgement).filter(Acknowledgement.submission_id == submission_id).order_by(Acknowledgement.received_at.desc()).first()
    if acknowledgement is None:
        raise HTTPException(status_code=404, detail="Acknowledgement not found.")
    return {
        "acknowledgement_id": acknowledgement.acknowledgement_id,
        "submission_id": acknowledgement.submission_id,
        "pha_id": acknowledgement.pha_id,
        "status": acknowledgement.status,
        "received_at": acknowledgement.received_at,
        "response": acknowledgement.response,
        "errors": acknowledgement.errors,
    }


@router.get("/api/submissions/{submission_id}/attempts")
def get_submission_attempts(submission_id: str, db: Session = Depends(get_db)) -> dict:
    _get_submission(db, submission_id)
    attempts = db.query(SubmissionAttempt).filter(SubmissionAttempt.original_submission_id == submission_id).order_by(SubmissionAttempt.attempt_number.asc()).all()
    return {
        "submission_id": submission_id,
        "attempts": [
            {
                "attempt_id": item.attempt_id,
                "attempt_number": item.attempt_number,
                "original_submission_id": item.original_submission_id,
                "new_submission_id": item.new_submission_id,
                "reason": item.reason,
                "status": item.status,
                "timestamp": item.created_at,
            }
            for item in attempts
        ],
    }


@router.get("/api/submissions/{submission_id}/reportability-response")
def get_submission_reportability(submission_id: str, db: Session = Depends(get_db)) -> dict:
    submission = _get_submission(db, submission_id)
    case = db.query(Case).filter(Case.case_id == submission.case_id).first()
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found.")
    return {
        "case_id": str(case.case_id),
        "decision": case.reportability_decision,
        "disease": case.disease,
        "jurisdiction": case.jurisdiction,
        "rule": case.rule_id,
        "evidence": {"clinical": case.clinical_evidence, "laboratory": case.laboratory_evidence, "ai": case.ai_evidence},
        "warnings": case.warnings or [],
    }
