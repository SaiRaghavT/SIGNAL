from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID

from sqlalchemy import String, cast, or_
from sqlalchemy.orm import Session

from backend.app.models.case import Case
from backend.app.models.deadline_escalation import DeadlineEscalation
from backend.app.models.follow_up import FollowUp
from backend.app.models.submissions import Submission
from backend.app.models.workflow_records import CaseWorkflowRecord
from backend.app.case.workflow_api import _validation
from .report_fields import available_case_report_fields, missing_report_fields

from .schemas import CaseDetailResponse, CaseListItem, CaseListResponse


def get_case_detail(db: Session, case_id: UUID) -> CaseDetailResponse | None:
    case = db.query(Case).filter(Case.case_id == case_id).first()
    if case is None:
        return None

    report_fields = available_case_report_fields(case)
    missing_fields, required_missing_fields = missing_report_fields(report_fields)
    warnings = [
        warning for warning in (case.warnings or [])
        if warning not in (
            "Provider information needs human completion.",
            "Facility name needs human completion.",
        )
        and "required reporting fields need human completion." not in warning
    ]
    if required_missing_fields:
        warnings.append(f"{len(required_missing_fields)} required reporting fields need human completion.")
    if any(not (case.provider or {}).get(field) for field in ("name", "phone", "address")):
        warnings.append("Provider information needs human completion.")
    if not (case.facility or {}).get("name"):
        warnings.append("Facility name needs human completion.")
    submission = (
        db.query(Submission)
        .filter(Submission.case_id == str(case.case_id))
        .order_by(Submission.created_at.desc())
        .first()
    )
    follow_up = (
        db.query(FollowUp)
        .filter(FollowUp.case_id == str(case.case_id))
        .order_by(FollowUp.created_at.desc())
        .first()
    )
    return CaseDetailResponse(
        case_id=str(case.case_id),
        candidate_id=case.candidate_id,
        disease=case.disease,
        jurisdiction=case.jurisdiction,
        jurisdiction_status=case.jurisdiction_status,
        status=case.status,
        reportability_decision=case.reportability_decision,
        reportability_evidence_status=case.reportability_evidence_status,
        final_decision=case.final_decision,
        rule_id=case.rule_id,
        warnings=warnings,
        patient=case.patient,
        facility=case.facility,
        provider=case.provider,
        clinical_evidence=case.clinical_evidence,
        laboratory_evidence=case.laboratory_evidence,
        ai_evidence=case.ai_evidence,
        report_fields=report_fields,
        missing_report_fields=missing_fields,
        required_missing_fields=required_missing_fields,
        created_at=case.created_at,
        updated_at=case.updated_at,
        deadline=getattr(case, "deadline", None),
        severity=getattr(case, "severity", None),
        submission=(
            {
                "submission_id": submission.submission_id,
                "status": submission.status,
                "destination": submission.destination,
                "created_at": submission.created_at,
                "updated_at": submission.updated_at,
            }
            if submission
            else None
        ),
        follow_up=(
            {
                "followup_id": follow_up.followup_id,
                "status": follow_up.status,
                "next_action": follow_up.next_action,
                "due_date": follow_up.due_date,
            }
            if follow_up
            else None
        ),
    )


def list_cases(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    status: str | None = None,
    disease: str | None = None,
    jurisdiction: str | None = None,
    patient_id: str | None = None,
    search: str | None = None,
    priority: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> CaseListResponse:
    query = db.query(Case)

    if status is not None:
        query = query.filter(Case.status == status)
    if disease is not None:
        query = query.filter(Case.disease == disease)
    if jurisdiction is not None:
        query = query.filter(Case.jurisdiction == jurisdiction)
    if patient_id is not None:
        query = query.filter(Case.patient["patient_id"].as_string() == patient_id)
    if search and search.strip():
        pattern = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Case.candidate_id.ilike(pattern),
                Case.disease.ilike(pattern),
                cast(Case.patient, String).ilike(pattern),
            )
        )
    if priority:
        query = query.filter(Case.severity == priority.upper())
    if date_from:
        query = query.filter(
            Case.created_at >= datetime.combine(date_from, time.min, tzinfo=timezone.utc)
        )
    if date_to:
        query = query.filter(
            Case.created_at < datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=timezone.utc)
        )

    total = query.count()
    records = (
        query.order_by(Case.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = [
        CaseListItem(
            case_id=str(case.case_id),
            candidate_id=case.candidate_id,
            disease=case.disease,
            jurisdiction=case.jurisdiction,
            status=case.status,
            reportability_decision=case.reportability_decision,
            final_decision=case.final_decision,
            rule_id=case.rule_id,
            created_at=case.created_at,
            updated_at=case.updated_at,
            warnings=case.warnings or [],
            severity=getattr(case, "severity", None),
            deadline=getattr(case, "deadline", None),
        )
        for case in records
    ]

    all_cases = db.query(Case).all()
    at_risk_ids = {
        str(case.case_id)
        for case in all_cases
        if case.deadline is not None
        and str(case.severity or "").upper() in {"HIGH", "CRITICAL"}
    }
    at_risk_ids.update(
        str(case_id)
        for (case_id,) in db.query(DeadlineEscalation.case_id)
        .filter(DeadlineEscalation.status == "UPCOMING")
        .distinct()
        .all()
    )
    at_risk_ids.intersection_update(str(case.case_id) for case in all_cases)
    case_by_id = {str(case.case_id): case for case in all_cases}
    readiness_rows = db.query(CaseWorkflowRecord.case_id, CaseWorkflowRecord.status).filter(
        CaseWorkflowRecord.record_type == "SUBMISSION_READINESS"
    ).order_by(CaseWorkflowRecord.created_at.desc()).all()
    latest_readiness: dict[str, str] = {}
    for case_id, status_value in readiness_rows:
        latest_readiness.setdefault(str(case_id), str(status_value or "").upper())
    ready_case_ids = {
        case_id
        for case_id, readiness_status in latest_readiness.items()
        if readiness_status == "READY"
        and case_id in case_by_id
        and _validation(case_by_id[case_id])["valid"]
    }
    review_case_ids = {
        str(case.case_id)
        for case in all_cases
        if any(
            str(value or "").strip().upper() == "NEEDS_REVIEW"
            for value in (
                case.status,
                case.final_decision,
                case.reportability_decision,
                case.jurisdiction_status,
            )
        )
    }
    for item in items:
        item.needs_review = item.case_id in review_case_ids
        item.deadline_risk = item.case_id in at_risk_ids
        item.report_ready = item.case_id in ready_case_ids

    return CaseListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        metrics={
            "candidate_cases": len(all_cases),
            "at_risk_deadlines": len(at_risk_ids),
            "needs_review": len(review_case_ids),
            "report_ready": len(ready_case_ids),
        },
    )
