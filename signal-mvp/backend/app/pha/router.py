
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.agents.acknowledgement.schemas import AcknowledgementRequest
from backend.app.agents.acknowledgement.service import AcknowledgementService
from backend.app.database import get_db
from backend.app.models.submissions import Submission
from backend.app.models.case import Case
from backend.app.models.workflow_records import Acknowledgement, Report
from backend.app.models.pha_review_decision import PHAReviewDecision

router = APIRouter(
    prefix="/api/pha",
    tags=["Mock PHA"],
)


class PHAReviewRequest(BaseModel):
    decision: Literal["ACCEPTED", "REJECTED", "INFORMATION_REQUESTED"]
    reviewer: str = Field(min_length=1, max_length=255)
    reason: str | None = None
    requested_information: str | None = None


def get_case(db: Session, case_id: str) -> Case | None:
    return (
        db.query(Case)
        .filter(Case.case_id == case_id)
        .first()
    )


def get_patient_data(db: Session, case_id: str) -> dict:
    case = get_case(db, case_id)

    if case is None or not isinstance(case.patient, dict):
        return {}

    return case.patient


def get_patient_name(db: Session, case_id: str) -> str | None:
    patient = get_patient_data(db, case_id)

    first_name = patient.get("first_name") or patient.get("firstName") or ""
    last_name = patient.get("last_name") or patient.get("lastName") or ""

    name = f"{first_name} {last_name}".strip()
    return (
        name
        or patient.get("patient_name")
        or patient.get("patientName")
        or patient.get("full_name")
        or patient.get("display_name")
        or patient.get("name")
        or None
    )


def get_patient_key(db: Session, submission: Submission) -> str:
    patient = get_patient_data(db, submission.case_id)

    for field in (
        "patient_id",
        "patientId",
        "source_patient_id",
        "sourcePatientId",
    ):
        value = patient.get(field)
        if value is not None and str(value).strip():
            return str(value).strip()

    return str(submission.case_id)


def get_submission(db: Session, submission_id: str) -> Submission:
    submission = (
        db.query(Submission)
        .filter(
            Submission.submission_id == submission_id,
            Submission.destination == "MOCK_PHA",
        )
        .first()
    )

    if submission is None:
        raise HTTPException(
            status_code=404,
            detail="Mock PHA submission not found.",
        )

    return submission


def serialize_decision(decision: PHAReviewDecision) -> dict:
    return {
        "decision_id": decision.decision_id,
        "submission_id": decision.submission_id,
        "decision": decision.decision,
        "reviewer": decision.reviewer,
        "reason": decision.reason,
        "requested_information": decision.requested_information,
        "created_at": decision.created_at,
    }


@router.get("/reports")
def list_incoming_reports(
    db: Session = Depends(get_db),
):
    """List the latest submission for each unique patient."""

    submissions = (
        db.query(Submission)
        .filter(
            Submission.destination == "MOCK_PHA",
            Submission.status.in_(["SUBMITTED", "ACKNOWLEDGED"]),
        )
        .order_by(
            Submission.created_at.desc(),
            Submission.submission_id.desc(),
        )
        .all()
    )

    latest_by_patient = {}

    for submission in submissions:
        patient_key = get_patient_key(db, submission)
        if patient_key not in latest_by_patient:
            latest_by_patient[patient_key] = submission

    reports = []

    for submission in latest_by_patient.values():
        reports.append(
            {
                "submission_id": submission.submission_id,
                "case_id": submission.case_id,
                "report_id": submission.report_id,
                "ecr_id": submission.ecr_id,
                "destination": submission.destination,
                "status": submission.status,
                "channel": submission.channel,
                "created_at": submission.created_at,
                "pha_case_id": submission.pha_case_id,
                "patient_name": get_patient_name(db, submission.case_id),
            }
        )

    return {"count": len(reports), "reports": reports}


@router.get("/reports/{submission_id}")
def get_incoming_report(
    submission_id: str,
    db: Session = Depends(get_db),
):
    """Retrieve a submitted report and its latest PHA review decision."""

    submission = get_submission(db, submission_id)

    latest_decision = (
        db.query(PHAReviewDecision)
        .filter(PHAReviewDecision.submission_id == submission_id)
        .order_by(
            PHAReviewDecision.created_at.desc(),
            PHAReviewDecision.decision_id.desc(),
        )
        .first()
    )
    acknowledgement = (
        db.query(Acknowledgement)
        .filter(Acknowledgement.submission_id == submission_id)
        .order_by(Acknowledgement.received_at.desc())
        .first()
    )

    report = (
        db.query(Report)
        .filter(Report.report_id == submission.report_id)
        .first()
        if submission.report_id else None
    )
    ecr_payload = dict(submission.ecr_payload or {})
    ecr_payload.setdefault("report_form", {
        "report_id": report.report_id,
        "form_id": report.form_id,
        "form_version": report.form_version,
        "document_url": (
            f"/api/agents/form-rendering/{report.render_id}"
            if report.render_id else None
        ),
    } if report else {})

    return {
        "submission_id": submission.submission_id,
        "case_id": submission.case_id,
        "report_id": submission.report_id,
        "ecr_id": submission.ecr_id,
        "destination": submission.destination,
        "status": submission.status,
        "acknowledgement": ({
            "acknowledgement_id": acknowledgement.acknowledgement_id,
            "status": acknowledgement.status,
            "received_at": acknowledgement.received_at,
            "pha_case_id": acknowledgement.pha_id,
        } if acknowledgement else None),
        "channel": submission.channel,
        "created_at": submission.created_at,
        "pha_case_id": submission.pha_case_id,
        "patient_name": get_patient_name(db, submission.case_id),
        "patient": get_patient_data(db, submission.case_id),
        "ecr_payload": ecr_payload,
        "latest_pha_decision": (
            serialize_decision(latest_decision)
            if latest_decision
            else None
        ),
    }


@router.post("/reports/{submission_id}/acknowledgement", status_code=201)
def acknowledge_incoming_report(
    submission_id: str,
    db: Session = Depends(get_db),
):
    """Record a Mock PHA receipt acknowledgement on the SIGNAL submission."""
    get_submission(db, submission_id)
    try:
        result = AcknowledgementService().process_acknowledgement(
            AcknowledgementRequest(submission_id=submission_id), db
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if result.status != "ACKNOWLEDGED":
        raise HTTPException(
            status_code=409,
            detail={"message": "The report cannot be acknowledged.", "result": result.model_dump(mode="json")},
        )
    return result.model_dump(mode="json")


@router.post("/reports/{submission_id}/decision", status_code=201)
def record_pha_decision(
    submission_id: str,
    request: PHAReviewRequest,
    db: Session = Depends(get_db),
):
    """Record a Mock PHA decision without changing submission status."""

    submission = get_submission(db, submission_id)

    reason = request.reason.strip() if request.reason else None
    requested_information = (
        request.requested_information.strip()
        if request.requested_information
        else None
    )

    if request.decision == "REJECTED" and not reason:
        raise HTTPException(
            status_code=422,
            detail="A reason is required when rejecting a report.",
        )

    if request.decision == "INFORMATION_REQUESTED" and not requested_information:
        raise HTTPException(
            status_code=422,
            detail="Requested information is required for this decision.",
        )

    decision = PHAReviewDecision(
        submission_id=submission.submission_id,
        decision=request.decision,
        reviewer=request.reviewer.strip(),
        reason=reason,
        requested_information=requested_information,
    )

    try:
        db.add(decision)
        db.commit()
        db.refresh(decision)
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Unable to save the PHA review decision.",
        )

    return serialize_decision(decision)


@router.get("/reports/{submission_id}/decisions")
def list_pha_decisions(
    submission_id: str,
    db: Session = Depends(get_db),
):
    """Return the review decision history for a submission."""

    get_submission(db, submission_id)

    decisions = (
        db.query(PHAReviewDecision)
        .filter(PHAReviewDecision.submission_id == submission_id)
        .order_by(
            PHAReviewDecision.created_at.desc(),
            PHAReviewDecision.decision_id.desc(),
        )
        .all()
    )

    return {
        "submission_id": submission_id,
        "count": len(decisions),
        "decisions": [
            serialize_decision(decision)
            for decision in decisions
        ],
    }
