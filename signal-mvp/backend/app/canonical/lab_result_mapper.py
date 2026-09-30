from datetime import datetime
from typing import Any
from uuid import UUID

from backend.app.models.lab_result import LabResult


def parse_fhir_datetime(
    value: str | None,
) -> datetime | None:
    if not value:
        return None

    try:
        return datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )
    except ValueError:
        return None


def extract_codeable_concept(
    data: dict[str, Any] | None,
) -> tuple[str | None, str | None, str | None]:

    if not isinstance(data, dict):
        return None, None, None

    coding = data.get("coding") or []

    if coding:

        first_coding = coding[0]

        if isinstance(first_coding, dict):

            return (
                first_coding.get("system"),
                first_coding.get("code"),
                first_coding.get("display"),
            )

    return None, None, data.get("text")


def extract_observation_references(
    resource: dict[str, Any],
) -> list[str]:
    """
    Extract Observation source IDs from DiagnosticReport.result[].

    Supports common FHIR reference formats:

        Observation/123

        urn:uuid:123

        https://example.org/fhir/Observation/123
    """

    references: list[str] = []

    results = resource.get("result") or []

    for result in results:

        if not isinstance(result, dict):
            continue

        reference = result.get("reference")

        if not isinstance(reference, str):
            continue

        reference = reference.strip()

        if not reference:
            continue

        # -----------------------------------------------------
        # Relative FHIR reference
        #
        # Observation/123
        # -----------------------------------------------------

        prefix = "Observation/"

        if reference.startswith(prefix):

            observation_id = reference[len(prefix):]

            if observation_id:
                references.append(observation_id)

            continue

        # -----------------------------------------------------
        # Bundle-local UUID reference
        #
        # urn:uuid:123
        # -----------------------------------------------------

        urn_prefix = "urn:uuid:"

        if reference.startswith(urn_prefix):

            observation_id = reference[len(urn_prefix):]

            if observation_id:
                references.append(observation_id)

            continue

        # -----------------------------------------------------
        # Absolute FHIR reference
        #
        # https://example.org/fhir/Observation/123
        # -----------------------------------------------------

        marker = "/Observation/"

        if marker in reference:

            observation_id = reference.rsplit(
                marker,
                1,
            )[1]

            if observation_id:
                references.append(observation_id)

    return references


def map_fhir_diagnostic_report(
    resource: dict[str, Any],
    patient_id: UUID,
    encounter_id: UUID | None,
    source: str,
) -> tuple[LabResult, list[str]]:

    if resource.get("resourceType") != "DiagnosticReport":
        raise ValueError(
            "Expected a FHIR DiagnosticReport resource."
        )

    source_lab_result_id = resource.get("id")

    if not source_lab_result_id:
        raise ValueError(
            "FHIR DiagnosticReport resource is missing its id."
        )

    # ---------------------------------------------------------
    # DiagnosticReport.code
    # ---------------------------------------------------------

    test_system, test_code, test_display = (
        extract_codeable_concept(
            resource.get("code")
        )
    )

    # ---------------------------------------------------------
    # DiagnosticReport.category
    # ---------------------------------------------------------

    category = None

    categories = resource.get("category") or []

    if categories:

        first_category = categories[0]

        if isinstance(first_category, dict):

            (
                _,
                category_code,
                category_display,
            ) = extract_codeable_concept(
                first_category
            )

            category = (
                category_display
                or category_code
            )

    # ---------------------------------------------------------
    # DiagnosticReport.performer
    # ---------------------------------------------------------

    performer_reference = None

    performers = resource.get("performer") or []

    if performers:

        first_performer = performers[0]

        if isinstance(first_performer, dict):

            performer_reference = (
                first_performer.get("reference")
            )

    # ---------------------------------------------------------
    # Create canonical LabResult
    # ---------------------------------------------------------

    lab_result = LabResult(
        source_lab_result_id=source_lab_result_id,
        patient_id=patient_id,
        encounter_id=encounter_id,
        test_code=test_code,
        test_system=test_system,
        test_display=test_display,
        report_status=resource.get("status"),
        category=category,
        effective_time=parse_fhir_datetime(
            resource.get("effectiveDateTime")
        ),
        issued_time=parse_fhir_datetime(
            resource.get("issued")
        ),
        performer_reference=performer_reference,
        conclusion=resource.get("conclusion"),
        source=source,
        source_resource="DiagnosticReport",
    )

    # ---------------------------------------------------------
    # Resolve DiagnosticReport.result[]
    # ---------------------------------------------------------

    observation_source_ids = (
        extract_observation_references(resource)
    )

    return (
        lab_result,
        observation_source_ids,
    )