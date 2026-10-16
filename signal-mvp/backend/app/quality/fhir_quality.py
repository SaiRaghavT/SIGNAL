from typing import Any


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


def _extract_reference_id(
    reference: str | None,
    resource_type: str,
) -> str | None:
    """
    Extract the source resource ID from common FHIR references.

    Supported:

        Patient/123
        urn:uuid:123
        https://example.org/fhir/Patient/123
    """

    if not isinstance(reference, str):
        return None

    reference = reference.strip()

    if not reference:
        return None

    # Relative reference
    prefix = f"{resource_type}/"

    if reference.startswith(prefix):
        return reference[len(prefix):]

    # Bundle-local UUID
    urn_prefix = "urn:uuid:"

    if reference.startswith(urn_prefix):
        return reference[len(urn_prefix):]

    # Absolute reference
    marker = f"/{resource_type}/"

    if marker in reference:
        return reference.rsplit(marker, 1)[1]

    return None


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
) -> list[FHIRQualityIssue]:

    issues: list[FHIRQualityIssue] = []

    patient_ids = {
        resource.get("id")
        for resource in resources.get("Patient", [])
        if resource.get("id")
    }

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

            patient_source_id = _extract_reference_id(
                reference,
                "Patient",
            )

            if not patient_source_id:

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

            if patient_source_id not in patient_ids:

                issues.append(
                    FHIRQualityIssue(
                        severity="error",
                        resource_type=resource_type,
                        resource_id=resource_id,
                        field="subject.reference",
                        message=(
                            f"{resource_type} "
                            f"{resource_id} references unknown "
                            f"Patient/{patient_source_id}."
                        ),
                    )
                )

    return issues


def _check_encounter_references(
    resources: dict[str, list[dict[str, Any]]],
) -> list[FHIRQualityIssue]:

    issues: list[FHIRQualityIssue] = []

    encounter_ids = {
        resource.get("id")
        for resource in resources.get("Encounter", [])
        if resource.get("id")
    }

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

            encounter_source_id = None

            if isinstance(reference_data, dict):
                encounter_source_id = _extract_reference_id(
                    reference_data.get("reference"),
                    "Encounter",
                )

            if not encounter_source_id:

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

            if encounter_source_id not in encounter_ids:

                issues.append(
                    FHIRQualityIssue(
                        severity="error",
                        resource_type=resource_type,
                        resource_id=resource_id,
                        field="encounter.reference",
                        message=(
                            f"{resource_type} "
                            f"{resource_id} references unknown "
                            f"Encounter/{encounter_source_id}."
                        ),
                    )
                )

    return issues


def _check_document_encounter_references(
    resources: dict[str, list[dict[str, Any]]],
) -> list[FHIRQualityIssue]:

    issues: list[FHIRQualityIssue] = []

    encounter_ids = {
        resource.get("id")
        for resource in resources.get("Encounter", [])
        if resource.get("id")
    }

    for resource in resources.get("DocumentReference", []):

        resource_id = resource.get("id")

        context = resource.get("context")

        if not isinstance(context, dict):
            continue

        encounter_references = context.get("encounter") or []

        for reference_data in encounter_references:

            if not isinstance(reference_data, dict):
                issues.append(
                    FHIRQualityIssue(
                        severity="error",
                        resource_type="DocumentReference",
                        resource_id=resource_id,
                        field="context.encounter",
                        message=(
                            "DocumentReference contains an "
                            "invalid Encounter reference."
                        ),
                    )
                )
                continue

            encounter_source_id = _extract_reference_id(
                reference_data.get("reference"),
                "Encounter",
            )

            if not encounter_source_id:
                issues.append(
                    FHIRQualityIssue(
                        severity="error",
                        resource_type="DocumentReference",
                        resource_id=resource_id,
                        field="context.encounter",
                        message=(
                            "DocumentReference contains an "
                            "invalid Encounter reference."
                        ),
                    )
                )
                continue

            if encounter_source_id not in encounter_ids:
                issues.append(
                    FHIRQualityIssue(
                        severity="error",
                        resource_type="DocumentReference",
                        resource_id=resource_id,
                        field="context.encounter",
                        message=(
                            f"DocumentReference {resource_id} "
                            f"references unknown "
                            f"Encounter/{encounter_source_id}."
                        ),
                    )
                )

    return issues


def validate_fhir_data_quality(
    resources: dict[str, list[dict[str, Any]]],
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
        _check_patient_references(resources)
    )

    # ---------------------------------------------------------
    # Encounter reference validation
    # ---------------------------------------------------------

    issues.extend(
        _check_encounter_references(resources)
    )

    # ---------------------------------------------------------
    # DocumentReference encounter validation
    # ---------------------------------------------------------

    issues.extend(
        _check_document_encounter_references(resources)
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