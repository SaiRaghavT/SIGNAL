from typing import Any


class FHIRValidationError(ValueError):
    """Raised when an incoming FHIR payload is invalid."""


def validate_fhir_bundle(payload: dict[str, Any]) -> None:
    """
    Validate the minimum structure required for a FHIR Bundle.

    This performs structural validation only.
    Full FHIR resource/profile validation can be added later.
    """

    if not isinstance(payload, dict):
        raise FHIRValidationError(
            "FHIR payload must be a JSON object."
        )

    resource_type = payload.get("resourceType")

    if resource_type != "Bundle":
        raise FHIRValidationError(
            "FHIR payload must have resourceType='Bundle'."
        )

    entries = payload.get("entry")

    if entries is None:
        return

    if not isinstance(entries, list):
        raise FHIRValidationError(
            "FHIR Bundle 'entry' must be a list."
        )

    for index, entry in enumerate(entries):

        if not isinstance(entry, dict):
            raise FHIRValidationError(
                f"Bundle entry at index {index} must be an object."
            )

        resource = entry.get("resource")

        if resource is None:
            continue

        if not isinstance(resource, dict):
            raise FHIRValidationError(
                f"Bundle resource at index {index} must be an object."
            )

        if "resourceType" not in resource:
            raise FHIRValidationError(
                f"Bundle resource at index {index} "
                "is missing resourceType."
            )