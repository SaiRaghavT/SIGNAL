from .models import ECRPayload


def build_ecr(case) -> ECRPayload:
    warnings = []

    if case.status == "ON_HOLD":
        warnings.append(
            "Case is on hold; ECR cannot proceed to submission."
        )

    if case.status == "NEEDS_REVIEW":
        warnings.append(
            "Case requires review before submission."
        )

    if not case.jurisdiction:
        warnings.append("Jurisdiction is missing.")

    if not case.disease:
        warnings.append("Disease information is missing.")

    if case.status in {
        "READY_FOR_RULES",
        "ON_HOLD",
        "NEEDS_REVIEW",
    }:
        status = case.status
    else:
        status = "DRAFT"

    return ECRPayload(
        ecr_id=f"ECR-{case.case_id}",
        case_id=case.case_id,
        candidate_id=case.candidate_id,
        jurisdiction=case.jurisdiction,
        disease=case.disease,
        patient=case.patient,
        facility=case.facility,
        provider=case.provider,
        clinical_evidence=case.clinical_evidence,
        laboratory_evidence=case.laboratory_evidence,
        ai_evidence=case.ai_evidence,
        reportability_decision=case.reportability_decision,
        reportability_evidence_status=(
            case.reportability_evidence_status
        ),
        status=status,
        warnings=warnings,
    )
