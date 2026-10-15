from collections import defaultdict
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit


SUPPORTED_RESOURCE_TYPES = {
    "Patient",
    "Encounter",
    "Condition",
    "Observation",
    "DiagnosticReport",
    "DocumentReference",
}


@dataclass(frozen=True)
class BundleReferenceResolution:
    resource: dict[str, Any] | None
    reference_id: str | None
    error: str | None = None
    actual_resource_type: str | None = None


class BundleReferenceIndex:
    """Resolve references against resource IDs and Bundle entry fullUrls."""

    def __init__(self, entries: list[dict[str, Any]] | None = None):
        self.by_full_url: dict[str, dict[str, Any]] = {}
        self.by_type_and_id: dict[tuple[str, str], dict[str, Any]] = {}

        for entry in entries or []:
            if not isinstance(entry, dict):
                continue
            resource = entry.get("resource")
            if not isinstance(resource, dict):
                continue

            resource_type = resource.get("resourceType")
            resource_id = resource.get("id")
            full_url = entry.get("fullUrl")
            if isinstance(resource_type, str) and isinstance(resource_id, str):
                self.by_type_and_id.setdefault((resource_type, resource_id), resource)
            if isinstance(full_url, str) and full_url:
                self.by_full_url.setdefault(full_url, resource)

    @classmethod
    def from_resources(cls, resources: dict[str, list[dict[str, Any]]]):
        """Build an ID-only index for callers that have no original Bundle entries."""
        entries = [
            {"resource": resource}
            for resource_list in resources.values()
            for resource in resource_list
        ]
        return cls(entries)

    def resolve(
        self,
        reference: str | None,
        expected_resource_type: str,
    ) -> BundleReferenceResolution:
        if not isinstance(reference, str) or not reference.strip():
            return BundleReferenceResolution(None, None, "malformed")

        reference = reference.strip()
        full_url_target = self.by_full_url.get(reference)
        if full_url_target is not None:
            target_type = full_url_target.get("resourceType")
            target_id = full_url_target.get("id")
            if target_type != expected_resource_type:
                return BundleReferenceResolution(
                    None,
                    target_id if isinstance(target_id, str) else None,
                    "wrong_type",
                    target_type if isinstance(target_type, str) else None,
                )
            return BundleReferenceResolution(
                full_url_target,
                target_id if isinstance(target_id, str) else None,
            )

        # An unresolved URN is a missing Bundle-local target, not a valid
        # reference merely because it has the expected prefix. Some producers
        # also use the resource ID itself as the UUID, so check that index too.
        if reference.lower().startswith("urn:uuid:"):
            reference_id = reference[len("urn:uuid:"):]
            target = self.by_type_and_id.get((expected_resource_type, reference_id))
            if target is not None:
                return BundleReferenceResolution(target, reference_id)

            actual_type_target = next(
                (
                    (resource_type, resource)
                    for (resource_type, resource_id), resource in self.by_type_and_id.items()
                    if resource_id == reference_id
                ),
                None,
            )
            if actual_type_target is not None:
                actual_type, _ = actual_type_target
                return BundleReferenceResolution(
                    None,
                    reference_id,
                    "wrong_type",
                    actual_type,
                )
            return BundleReferenceResolution(
                None, reference_id, "missing", expected_resource_type
            )

        path = urlsplit(reference).path if "://" in reference else reference
        segments = [segment for segment in path.split("/") if segment]
        if len(segments) < 2:
            return BundleReferenceResolution(None, None, "malformed")

        referenced_type, reference_id = segments[-2], segments[-1]
        if referenced_type != expected_resource_type:
            return BundleReferenceResolution(
                None,
                reference_id,
                "wrong_type",
                referenced_type,
            )

        target = self.by_type_and_id.get((expected_resource_type, reference_id))
        if target is None:
            return BundleReferenceResolution(None, reference_id, "missing", expected_resource_type)
        return BundleReferenceResolution(target, reference_id)


def build_bundle_reference_index(entries: list[dict[str, Any]] | None) -> BundleReferenceIndex:
    return BundleReferenceIndex(entries)


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
