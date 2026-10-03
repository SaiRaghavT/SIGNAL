from uuid import UUID

from sqlalchemy.orm import Session

from backend.app.models.case import Case
from .report_fields import missing_report_fields

from .schemas import CaseDetailResponse, CaseListItem, CaseListResponse


def get_case_detail(db: Session, case_id: UUID) -> CaseDetailResponse | None:
    case = db.query(Case).filter(Case.case_id == case_id).first()
    if case is None:
        return None

    report_fields = getattr(case, "report_fields", {}) or {}
    missing_fields, required_missing_fields = missing_report_fields(report_fields)
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
        warnings=case.warnings or [],
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
        )
        for case in records
    ]

    return CaseListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )
