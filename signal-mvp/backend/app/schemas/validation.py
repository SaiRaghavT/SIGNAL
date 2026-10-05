from dataclasses import dataclass, field
from typing import Any, List


@dataclass
class ValidationResult:
    valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    completion_required: List[str] = field(default_factory=list)


def validate_ecr(ecr: Any, smart_fields: Any = None) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []
    completion_required: list[str] = []

    # Structural errors indicate malformed workflow output rather than
    # information that a reporting user can supply.
    if not ecr.ecr_id:
        errors.append("ECR ID is missing.")
    if not ecr.case_id:
        errors.append("Case ID is missing.")
    if not ecr.candidate_id:
        errors.append("Candidate ID is missing.")

    if not ecr.jurisdiction:
        completion_required.append("Jurisdiction must be resolved.")
    if not ecr.disease:
        completion_required.append("Disease information must be completed.")

    if not ecr.patient:
        completion_required.append("Patient information is missing.")
    if not (ecr.patient.get("dob") or ecr.patient.get("date_of_birth")):
        completion_required.append("Patient date of birth is missing.")

    if not ecr.facility.get("name"):
        completion_required.append("Facility name is missing.")
    missing_provider_fields = [
        name for name in ("name", "phone", "address")
        if not ecr.provider.get(name)
    ]
    if missing_provider_fields:
        completion_required.append(
            "Provider information requires completion: "
            + ", ".join(missing_provider_fields)
            + "."
        )

    if not ecr.clinical_evidence:
        completion_required.append("Clinical evidence requires human completion.")
    if not ecr.laboratory_evidence:
        completion_required.append("Laboratory evidence is missing.")
    if not ecr.reportability_decision:
        completion_required.append("Reportability decision is missing.")
    if not ecr.reportability_evidence_status:
        completion_required.append("Reportability evidence status is missing.")

    if smart_fields is not None:
        completion_required.extend(smart_fields.required_missing_fields)
        optional_missing = set(smart_fields.missing_fields) - set(smart_fields.required_missing_fields)
        warnings.extend(f"Optional report field is missing: {name}" for name in sorted(optional_missing))

    if ecr.status in {"HOLD", "NEEDS_REVIEW"}:
        warnings.append(
            f"ECR status is {ecr.status}; submission should not proceed."
        )

    completion_required = list(dict.fromkeys(completion_required))
    return ValidationResult(
        valid=not errors and not completion_required,
        errors=errors,
        warnings=warnings,
        completion_required=completion_required,
    )
