from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.case import Case
from backend.app.models.submissions import Submission
from backend.app.models.workflow_records import Acknowledgement, CaseWorkflowRecord, SubmissionAttempt
from backend.app.models.audit_event import AuditEvent

router = APIRouter(tags=["Submissions"])


def _clinical_tracking_rows(db: Session) -> list[dict]:
    """Combine persisted admin handoffs with persisted PHA transmission records."""
    cases = db.query(Case).all()
    case_ids = [str(case.case_id) for case in cases]
    if not case_ids:
        return []

    workflow_rows = (
        db.query(CaseWorkflowRecord)
        .filter(CaseWorkflowRecord.case_id.in_(case_ids))
        .filter(CaseWorkflowRecord.record_type.in_(("ADMIN_QUEUE", "REVIEW")))
        .order_by(CaseWorkflowRecord.created_at.desc())
        .all()
    )
    latest_queue: dict[str, CaseWorkflowRecord] = {}
    latest_admin_review: dict[str, CaseWorkflowRecord] = {}
    for row in workflow_rows:
        if row.record_type == "ADMIN_QUEUE":
            latest_queue.setdefault(row.case_id, row)
        elif row.record_type == "REVIEW":
            payload = row.payload if isinstance(row.payload, dict) else {}
            role = str(payload.get("reviewer_role") or row.actor_id or "").casefold()
            if "admin" in role or "administrator" in role:
                latest_admin_review.setdefault(row.case_id, row)

    submissions = (
        db.query(Submission)
        .filter(Submission.case_id.in_(case_ids))
        .order_by(Submission.created_at.desc())
        .all()
    )
    submissions_by_case: dict[str, list[Submission]] = {}
    for submission in submissions:
        submissions_by_case.setdefault(str(submission.case_id), []).append(submission)

    result: list[dict] = []
    for case in cases:
        case_id = str(case.case_id)
        queue = latest_queue.get(case_id)
        queue_status = (queue.status if queue else "").upper()
        review = latest_admin_review.get(case_id)
        review_status = (review.status if review else "").upper()
        if review_status == "APPROVE":
            workflow_status = "Ready for Submission"
        elif review_status == "REQUEST_INFORMATION":
            workflow_status = "Returned for Correction"
        elif review_status == "REJECT":
            workflow_status = "Rejected"
        elif queue_status == "READY_FOR_SUBMISSION":
            workflow_status = "Ready for Submission"
        elif queue_status == "QUEUED":
            workflow_status = "Pending Admin Verification"
        elif queue_status == "FAILED":
            workflow_status = "Failed"
        elif queue_status == "DISPATCHED":
            workflow_status = "Submitted"
        else:
            workflow_status = queue_status.replace("_", " ").title() or "Not Queued"

        patient = case.patient if isinstance(case.patient, dict) else {}
        case_submissions = submissions_by_case.get(case_id, [])
        if case_submissions:
            for submission in case_submissions:
                status = (submission.status or "").upper()
                result.append({
                    "record_id": submission.submission_id,
                    "submission_id": submission.submission_id,
                    "case_id": case_id,
                    "patient": patient,
                    "disease": case.disease,
                    "jurisdiction": case.jurisdiction,
                    "destination": submission.destination,
                    "channel": submission.channel,
                    "status": status,
                    "workflow_status": {
                        "SUBMITTED": "Submitted",
                        "ACKNOWLEDGED": "Acknowledged",
                        "ACCEPTED": "Acknowledged",
                        "FAILED": "Failed",
                        "ERROR": "Failed",
                        "REJECTED": "Rejected",
                    }.get(status, status.replace("_", " ").title() or workflow_status),
                    "submitted_at": submission.created_at,
                    "created_at": submission.created_at,
                    "updated_at": submission.updated_at,
                    "submission_mode": submission.submission_mode or case.submission_mode,
                    "acknowledgement_id": submission.acknowledgement_id,
                    "pha_case_id": submission.pha_case_id,
                    "errors": submission.errors or [],
                })
        elif queue is not None:
            result.append({
                "record_id": f"QUEUE-{case_id}",
                "submission_id": None,
                "case_id": case_id,
                "patient": patient,
                "disease": case.disease,
                "jurisdiction": case.jurisdiction,
                "destination": case.jurisdiction,
                "channel": None,
                "status": queue_status or "QUEUED",
                "workflow_status": workflow_status,
                "submitted_at": None,
                "created_at": queue.created_at,
                "updated_at": queue.updated_at,
                "submission_mode": case.submission_mode,
                "acknowledgement_id": None,
                "pha_case_id": None,
                "errors": [],
            })

    return result


@router.get("/api/clinical/submissions")
def list_clinical_submission_tracking(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, max_length=200),
    status: str | None = Query(None, max_length=50),
    db: Session = Depends(get_db),
) -> dict:
    items = _clinical_tracking_rows(db)
    if status:
        items = [item for item in items if item["status"].casefold() == status.casefold()]
    if search and search.strip():
        needle = search.strip().casefold()
        items = [item for item in items if needle in " ".join(str(value or "") for value in (
            item["patient"].get("name"), item["patient"].get("full_name"),
            item["disease"], item["jurisdiction"], item["case_id"], item["submission_id"],
        )).casefold()]
    items.sort(key=lambda item: item["created_at"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    total = len(items)
    start = (page - 1) * page_size
    return {
        "items": items[start:start + page_size],
        "page": page,
        "page_size": page_size,
        "total": total,
        "pages": (total + page_size - 1) // page_size,
    }


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
        "submission_mode": submission.submission_mode,
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
