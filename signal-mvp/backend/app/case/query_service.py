from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID

from sqlalchemy import String, cast, or_
from sqlalchemy.orm import Session

from backend.app.models.case import Case
from backend.app.models.deadline_escalation import DeadlineEscalation
from backend.app.models.submissions import Submission
from backend.app.models.workflow_records import CaseWorkflowRecord
from backend.app.agents.deadline_calculation.service import DeadlineCalculationService
from backend.app.agents.deadline_escalation.service import DeadlineEscalationService
from backend.app.canonical.query_service import resolve_case_deadline
from backend.app.case.workflow_api import _validation
from backend.app.demo.synthetic_jordan_reporting import apply_synthetic_jordan_reporting_defaults
from backend.app.demo.admin_demo_reporting import (
    apply_admin_demo_reporting_defaults,
    canonical_patient_for_case,
)
from .report_fields import available_case_report_fields, missing_report_fields

from .schemas import CaseDetailResponse, CaseListItem, CaseListResponse


def get_case_detail(db: Session, case_id: UUID) -> CaseDetailResponse | None:
    case = db.query(Case).filter(Case.case_id == case_id).first()
    if case is None:
        return None

    # Normalize the checked-in synthetic Jordan fixture into its Case record
    # before returning it to Clinical Staff. The helper is exact-case scoped
    # and idempotent, so opening the form never creates another Case.
    demo_changes = apply_synthetic_jordan_reporting_defaults(case)
    demo_changes.extend(
        apply_admin_demo_reporting_defaults(case, canonical_patient_for_case(db, case))
    )
    if demo_changes:
        db.commit()
        db.refresh(case)

    report_fields = available_case_report_fields(case)
    laboratory_evidence = case.laboratory_evidence
    if isinstance(laboratory_evidence, dict):
        laboratory_evidence = [laboratory_evidence]
    elif not isinstance(laboratory_evidence, list):
        laboratory_evidence = []
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
    deadline_data, _deadline_reason = resolve_case_deadline(db, case)
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
        laboratory_evidence=laboratory_evidence,
        ai_evidence=case.ai_evidence,
        report_fields=report_fields,
        missing_report_fields=missing_fields,
        required_missing_fields=required_missing_fields,
        created_at=case.created_at,
        updated_at=case.updated_at,
        deadline=(deadline_data.get("deadline") if deadline_data else getattr(case, "deadline", None)),
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
                cast(Case.case_id, String).ilike(pattern),
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

    items = []
    for case in records:
        deadline_data, _deadline_reason = resolve_case_deadline(db, case)
        item = CaseListItem(
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
            deadline=(deadline_data.get("deadline") if deadline_data else getattr(case, "deadline", None)),
        )
        items.append(item)

    all_cases = db.query(Case).all()
    case_by_id = {str(case.case_id): case for case in all_cases}
    latest_escalations: dict[str, DeadlineEscalation] = {}
    for escalation in db.query(DeadlineEscalation).order_by(DeadlineEscalation.created_at.desc()).all():
        latest_escalations.setdefault(str(escalation.case_id), escalation)
    deadline_rules = DeadlineCalculationService()
    escalation_service = DeadlineEscalationService()
    for item in items:
        escalation = latest_escalations.get(item.case_id)
        if item.deadline is None and escalation is not None:
            item.deadline = escalation.deadline
        if item.severity is None and escalation is not None and item.deadline is not None:
            case = case_by_id.get(item.case_id)
            try:
                rule = deadline_rules._load_rule(
                    disease=(case.disease or item.disease or "") if case else (item.disease or ""),
                    jurisdiction=(escalation.jurisdiction or (case.jurisdiction if case else None) or item.jurisdiction or ""),
                    rule_id=escalation.rule_id,
                )
                item.severity = escalation_service.evaluate_current_state(item.deadline, rule)["urgency"]
            except ValueError:
                item.severity = None
    at_risk_ids = {
        str(case.case_id)
        for case in all_cases
        if getattr(case, "deadline", None) is not None
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
    readiness_rows = db.query(CaseWorkflowRecord).filter(
        CaseWorkflowRecord.record_type == "SUBMISSION_READINESS"
    ).order_by(CaseWorkflowRecord.created_at.desc()).all()
    latest_readiness: dict[str, str] = {}
    for row in readiness_rows:
        latest_readiness.setdefault(str(row.case_id), str(row.status or "").upper())
    ready_case_ids = {
        case_id
        for case_id, readiness_status in latest_readiness.items()
        if readiness_status == "READY"
        and case_id in case_by_id
        and _validation(case_by_id[case_id], db)["valid"]
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
                getattr(case, "jurisdiction_status", None),
            )
        )
    }
    for item in items:
        item.needs_review = item.case_id in review_case_ids
        item.deadline_risk = item.case_id in at_risk_ids
        item.report_ready = item.case_id in ready_case_ids
        if item.deadline is not None and str(item.severity or "").upper() in {"HIGH", "CRITICAL"}:
            item.deadline_risk = True
            at_risk_ids.add(item.case_id)

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
