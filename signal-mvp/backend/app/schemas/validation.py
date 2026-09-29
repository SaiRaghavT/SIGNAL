from dataclasses import dataclass, field
from typing import Any, List


@dataclass
class ValidationResult:
    valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def validate_ecr(ecr: Any) -> ValidationResult:
    errors = []
    warnings = []

    if not ecr.ecr_id:
        errors.append("ECR ID is missing.")

    if not ecr.case_id:
        errors.append("Case ID is missing.")

    if not ecr.candidate_id:
        errors.append("Candidate ID is missing.")

    if not ecr.jurisdiction:
        errors.append("Jurisdiction is missing.")

    if not ecr.disease:
        errors.append("Disease information is missing.")

    if not ecr.patient:
        errors.append("Patient information is missing.")

    if not ecr.facility:
        errors.append("Facility information is missing.")

    if not ecr.provider:
        warnings.append("Provider information is missing.")

    if not ecr.clinical_evidence:
        warnings.append("Clinical evidence is missing.")

    if not ecr.laboratory_evidence:
        warnings.append("Laboratory evidence is missing.")

    if not ecr.reportability_decision:
        errors.append("Reportability decision is missing.")

    if not ecr.reportability_evidence_status:
        errors.append("Reportability evidence status is missing.")

    if ecr.status in {"ON_HOLD", "NEEDS_REVIEW"}:
        warnings.append(
            f"ECR status is {ecr.status}; submission should not proceed."
        )

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )
