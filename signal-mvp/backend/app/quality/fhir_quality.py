from typing import Any

from backend.app.ingestion.fhir.parser import BundleReferenceIndex, build_bundle_reference_index


class FHIRQualityIssue:
    def __init__(
        self,
        severity: str,
        resource_type: str,
        resource_id: str | None,
        field: str,
        message: str,
    ):
        self.severity = severity
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.field = field
        self.message = message

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "field": self.field,
            "message": self.message,
        }


def _check_resource_ids(
    resources: list[dict[str, Any]],
) -> list[FHIRQualityIssue]:

    issues: list[FHIRQualityIssue] = []
    seen_ids: set[tuple[str, str]] = set()

    for resource in resources:

        resource_type = resource.get("resourceType")
        resource_id = resource.get("id")

        if not resource_type:
            issues.append(
                FHIRQualityIssue(
                    severity="error",
                    resource_type="Unknown",
                    resource_id=None,
                    field="resourceType",
                    message="FHIR resource is missing resourceType.",
                )
            )
            continue

        if not resource_id:
            issues.append(
                FHIRQualityIssue(
                    severity="error",
                    resource_type=resource_type,
                    resource_id=None,
                    field="id",
                    message=(
                        f"{resource_type} resource is missing its id."
                    ),
                )
            )
            continue

        resource_key = (
            resource_type,
            resource_id,
        )

        if resource_key in seen_ids:
            issues.append(
                FHIRQualityIssue(
                    severity="error",
                    resource_type=resource_type,
                    resource_id=resource_id,
                    field="id",
                    message=(
                        f"Duplicate {resource_type} resource ID "
                        f"'{resource_id}' found in Bundle."
                    ),
                )
            )

        seen_ids.add(resource_key)

    return issues


def _check_patient_references(
    resources: dict[str, list[dict[str, Any]]],
    reference_index: BundleReferenceIndex,
) -> list[FHIRQualityIssue]:

    issues: list[FHIRQualityIssue] = []

    resources_with_patient_reference = [
        "Encounter",
        "Condition",
        "Observation",
        "DiagnosticReport",
        "DocumentReference",
    ]

    for resource_type in resources_with_patient_reference:

        for resource in resources.get(resource_type, []):

            resource_id = resource.get("id")

            # -------------------------------------------------
            # DocumentReference uses "subject"
            # just like the other supported resources.
            # -------------------------------------------------

            reference_data = resource.get("subject")

            reference = None

            if isinstance(reference_data, dict):
                reference = reference_data.get("reference")

            resolution = reference_index.resolve(reference, "Patient")

            if resolution.error == "malformed":

                issues.append(
                    FHIRQualityIssue(
                        severity="error",
                        resource_type=resource_type,
                        resource_id=resource_id,
                        field="subject.reference",
                        message=(
                            f"{resource_type} "
                            f"{resource_id} does not contain "
                            "a valid Patient reference."
                        ),
                    )
                )

                continue

            elif resolution.error == "missing":

                issues.append(
                    FHIRQualityIssue(
                        severity="error",
                        resource_type=resource_type,
                        resource_id=resource_id,
                        field="subject.reference",
                        message=(
                            f"{resource_type} "
                            f"{resource_id} references unknown "
                            f"Patient/{resolution.reference_id}."
                        ),
                    )
                )
            elif resolution.error == "wrong_type":
                issues.append(
                    FHIRQualityIssue(
                        severity="error",
                        resource_type=resource_type,
                        resource_id=resource_id,
                        field="subject.reference",
                        message=(
                            f"{resource_type} {resource_id} references "
                            f"{resolution.actual_resource_type}/"
                            f"{resolution.reference_id}; expected Patient."
                        ),
                    )
                )

    return issues


def _check_encounter_references(
    resources: dict[str, list[dict[str, Any]]],
    reference_index: BundleReferenceIndex,
) -> list[FHIRQualityIssue]:

    issues: list[FHIRQualityIssue] = []

    resources_with_encounter_reference = [
        "Condition",
        "Observation",
        "DiagnosticReport",
    ]

    for resource_type in resources_with_encounter_reference:

        for resource in resources.get(resource_type, []):

            resource_id = resource.get("id")

            reference_data = resource.get("encounter")

            # Encounter is optional for these resources.
            if reference_data is None:
                continue

            reference = reference_data.get("reference") if isinstance(reference_data, dict) else None
            resolution = reference_index.resolve(reference, "Encounter")

            if resolution.error == "malformed":

                issues.append(
                    FHIRQualityIssue(
                        severity="error",
                        resource_type=resource_type,
                        resource_id=resource_id,
                        field="encounter.reference",
                        message=(
                            f"{resource_type} "
                            f"{resource_id} contains an invalid "
                            "Encounter reference."
                        ),
                    )
                )

                continue

            elif resolution.error == "missing":

                issues.append(
                    FHIRQualityIssue(
                        severity="error",
                        resource_type=resource_type,
                        resource_id=resource_id,
                        field="encounter.reference",
                        message=(
                            f"{resource_type} "
                            f"{resource_id} references unknown "
                            f"Encounter/{resolution.reference_id}."
                        ),
                    )
                )
            elif resolution.error == "wrong_type":
                issues.append(
                    FHIRQualityIssue(
                        severity="error",
                        resource_type=resource_type,
                        resource_id=resource_id,
                        field="encounter.reference",
                        message=(
                            f"{resource_type} {resource_id} references "
                            f"{resolution.actual_resource_type}/"
                            f"{resolution.reference_id}; expected Encounter."
                        ),
                    )
                )
    return issues


def _check_document_encounter_references(
    resources: dict[str, list[dict[str, Any]]],
    reference_index: BundleReferenceIndex,
) -> list[FHIRQualityIssue]:
    issues: list[FHIRQualityIssue] = []

    for resource in resources.get("DocumentReference", []):
        resource_id = resource.get("id")
        context = resource.get("context")
        if not isinstance(context, dict):
            continue

        for reference_data in context.get("encounter") or []:
            if not isinstance(reference_data, dict):
                issues.append(
                    FHIRQualityIssue(
                        severity="error",
                        resource_type="DocumentReference",
                        resource_id=resource_id,
                        field="context.encounter",
                        message="DocumentReference contains an invalid Encounter reference.",
                    )
                )
                continue

            resolution = reference_index.resolve(
                reference_data.get("reference"), "Encounter"
            )
            if resolution.error == "malformed":
                issues.append(
                    FHIRQualityIssue(
                        severity="error",
                        resource_type="DocumentReference",
                        resource_id=resource_id,
                        field="context.encounter",
                        message="DocumentReference contains an invalid Encounter reference.",
                    )
                )
            elif resolution.error == "missing":
                issues.append(
                    FHIRQualityIssue(
                        severity="error",
                        resource_type="DocumentReference",
                        resource_id=resource_id,
                        field="context.encounter",
                        message=(
                            f"DocumentReference {resource_id} references "
                            f"unknown Encounter/{resolution.reference_id}."
                        ),
                    )
                )
            elif resolution.error == "wrong_type":
                issues.append(
                    FHIRQualityIssue(
                        severity="error",
                        resource_type="DocumentReference",
                        resource_id=resource_id,
                        field="context.encounter",
                        message=(
                            f"DocumentReference {resource_id} references "
                            f"{resolution.actual_resource_type}/"
                            f"{resolution.reference_id}; expected Encounter."
                        ),
                    )
                )

    return issues


def validate_fhir_data_quality(
    resources: dict[str, list[dict[str, Any]]],
    bundle_entries: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Validate semantic/data-quality relationships inside
    a parsed FHIR Bundle.

    This is separate from structural FHIR validation.

    Returns:

        passed / failed
        error count
        warning count
        issue count
        detailed issues
    """

    issues: list[FHIRQualityIssue] = []
    reference_index = (
        build_bundle_reference_index(bundle_entries)
        if bundle_entries is not None
        else BundleReferenceIndex.from_resources(resources)
    )

    # Flatten all resources for ID validation.
    all_resources: list[dict[str, Any]] = []

    for resource_list in resources.values():
        all_resources.extend(resource_list)

    # ---------------------------------------------------------
    # Resource ID validation
    # ---------------------------------------------------------

    issues.extend(
        _check_resource_ids(all_resources)
    )

    # ---------------------------------------------------------
    # Patient reference validation
    # ---------------------------------------------------------

    issues.extend(
        _check_patient_references(resources, reference_index)
    )

    # ---------------------------------------------------------
    # Encounter reference validation
    # ---------------------------------------------------------

    issues.extend(
        _check_encounter_references(resources, reference_index)
    )

    # ---------------------------------------------------------
    # DocumentReference encounter validation
    # ---------------------------------------------------------

    issues.extend(
        _check_document_encounter_references(resources, reference_index)
    )

    # ---------------------------------------------------------
    # Calculate result
    # ---------------------------------------------------------

    error_count = sum(
        1
        for issue in issues
        if issue.severity == "error"
    )

    warning_count = sum(
        1
        for issue in issues
        if issue.severity == "warning"
    )

    return {
        "status": (
            "failed"
            if error_count > 0
            else "passed"
        ),
        "error_count": error_count,
        "warning_count": warning_count,
        "issue_count": len(issues),
        "issues": [
            issue.to_dict()
            for issue in issues
        ],
    }
