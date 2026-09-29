from collections import defaultdict
from typing import Any


SUPPORTED_RESOURCE_TYPES = {
    "Patient",
    "Encounter",
    "Condition",
    "Observation",
    "DiagnosticReport",
    "DocumentReference",
}


def parse_fhir_bundle(
    payload: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    """
    Parse a FHIR Bundle and group supported resources by resourceType.

    This function does not:
    - modify the resources
    - map them to canonical models
    - write to PostgreSQL
    - apply business rules
    - perform AI processing

    It only extracts and groups FHIR resources.
    """

    resources: dict[str, list[dict[str, Any]]] = defaultdict(list)

    entries = payload.get("entry", [])

    for entry in entries:
        if not isinstance(entry, dict):
            continue

        resource = entry.get("resource")

        if not isinstance(resource, dict):
            continue

        resource_type = resource.get("resourceType")

        if resource_type not in SUPPORTED_RESOURCE_TYPES:
            continue

        resources[resource_type].append(resource)

    return {
        resource_type: resources.get(resource_type, [])
        for resource_type in SUPPORTED_RESOURCE_TYPES
    }