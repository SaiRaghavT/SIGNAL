from sqlalchemy.orm import Session

from backend.app.models.case import Case

from .models import CaseAssemblyInput, SignalCase


def assemble_case(
    data: CaseAssemblyInput,
    db: Session,
) -> SignalCase:
    warnings = []

    if data.jurisdiction_status != "RESOLVED":
        warnings.append("Jurisdiction requires review.")

    if not data.patient:
        warnings.append("Patient information is missing.")

    if not data.disease:
        warnings.append("Disease information is missing.")

    final_decision = data.final_decision or data.reportability_decision

    if data.jurisdiction_status != "RESOLVED":
        final_decision = "NEEDS_REVIEW"

    status = final_decision

    case = Case(
        candidate_id=data.candidate_id,
        patient=data.patient,
        facility=data.facility,
        provider=data.provider,
        disease=data.disease,
        clinical_evidence=data.clinical_evidence,
        laboratory_evidence=data.laboratory_evidence,
        ai_evidence=data.ai_evidence,
        jurisdiction=data.jurisdiction,
        jurisdiction_status=data.jurisdiction_status,
        reportability_decision=data.reportability_decision,
        reportability_evidence_status=data.reportability_evidence_status,
        status=status,
        final_decision=final_decision,
        rule_id=data.rule_id,
        warnings=warnings,
    )

    db.add(case)
    db.commit()
    db.refresh(case)

    return SignalCase(
        case_id=str(case.case_id),
        candidate_id=case.candidate_id,
        patient=case.patient,
        facility=case.facility,
        provider=case.provider,
        disease=case.disease,
        clinical_evidence=case.clinical_evidence,
        laboratory_evidence=case.laboratory_evidence,
        ai_evidence=case.ai_evidence,
        jurisdiction=case.jurisdiction,
        jurisdiction_status=case.jurisdiction_status,
        reportability_decision=case.reportability_decision,
        reportability_evidence_status=case.reportability_evidence_status,
        status=case.status,
        warnings=case.warnings,
        final_decision=case.final_decision,
        rule_id=case.rule_id,
    )