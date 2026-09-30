from dataclasses import dataclass, field
from typing import Any, List


@dataclass
class ValidationResult:
    valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def validate_ecr(
    ecr: Any,
    smart_fields: Any = None,
) -> ValidationResult:
    errors = []
    warnings = []

    # ---------------------------------------------------------
    # ECR identity
    # ---------------------------------------------------------
    if not ecr.ecr_id:
        errors.append("ECR ID is missing.")

    if not ecr.case_id:
        errors.append("Case ID is missing.")

    if not ecr.candidate_id:
        errors.append("Candidate ID is missing.")

    # ---------------------------------------------------------
    # Reporting context
    # ---------------------------------------------------------
    if not ecr.jurisdiction:
        errors.append("Jurisdiction is missing.")

    if not ecr.disease:
        errors.append("Disease information is missing.")

    # ---------------------------------------------------------
    # Patient
    # ---------------------------------------------------------
    if not ecr.patient:
        errors.append("Patient information is missing.")
        errors.append("Patient date of birth is missing.")
    elif not (
        ecr.patient.get("dob")
        or ecr.patient.get("date_of_birth")
):
        errors.append("Patient date of birth is missing.")

    # ---------------------------------------------------------
    # Facility / provider
    # ---------------------------------------------------------
    if not ecr.facility:
        errors.append("Facility information is missing.")

    if not ecr.provider:
        errors.append("Provider information is missing.")

    # ---------------------------------------------------------
    # Evidence
    # ---------------------------------------------------------
    if not ecr.clinical_evidence:
        errors.append("Clinical evidence is missing.")

    if not ecr.laboratory_evidence:
        errors.append("Laboratory evidence is missing.")

    # ---------------------------------------------------------
    # Reportability
    # ---------------------------------------------------------
    if not ecr.reportability_decision:
        errors.append("Reportability decision is missing.")

    if not ecr.reportability_evidence_status:
        errors.append("Reportability evidence status is missing.")

    # ---------------------------------------------------------
    # Form-level validation from Agent 27
    # ---------------------------------------------------------
    if smart_fields is not None:

        # Required fields → validation errors
        for field_name in smart_fields.required_missing_fields:
            errors.append(
                f"Required report field is missing: {field_name}"
            )

        # Optional fields → validation warnings
        optional_missing_fields = set(
            smart_fields.missing_fields
        ) - set(
            smart_fields.required_missing_fields
        )

        for field_name in optional_missing_fields:
            warnings.append(
                f"Optional report field is missing: {field_name}"
            )

    # ---------------------------------------------------------
    # Workflow status
    # ---------------------------------------------------------
    if ecr.status in {"HOLD", "NEEDS_REVIEW"}:
        warnings.append(
            f"ECR status is {ecr.status}; "
            "submission should not proceed."
        )

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )