from .models import CaseAssemblyInput, SignalCase

def assemble_case(data: CaseAssemblyInput) -> SignalCase:
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

    return SignalCase(
        case_id=f"CASE-{data.candidate_id}",
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
        warnings=warnings,
        final_decision=final_decision,
        rule_id=data.rule_id,
    )
