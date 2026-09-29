from datetime import datetime
from typing import Any
from uuid import UUID

from backend.app.models.condition import Condition


def parse_fhir_datetime(
    value: str | None,
) -> datetime | None:
    """
    Convert a FHIR dateTime string into a Python datetime.
    """
    if not value:
        return None

    try:
        return datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )
    except ValueError:
        return None


def extract_coding(
    code_data: dict[str, Any] | None,
) -> tuple[str | None, str | None, str | None]:
    """
    Extract system, code, and display from a FHIR CodeableConcept.
    """

    if not isinstance(code_data, dict):
        return None, None, None

    coding = code_data.get("coding") or []

    if coding:
        first_coding = coding[0]

        if isinstance(first_coding, dict):
            return (
                first_coding.get("system"),
                first_coding.get("code"),
                first_coding.get("display"),
            )

    return (
        None,
        None,
        code_data.get("text"),
    )


def map_fhir_condition(
    resource: dict[str, Any],
    patient_id: UUID,
    encounter_id: UUID | None,
    source: str,
) -> Condition:
    """
    Convert a FHIR Condition resource into
    the SIGNAL Condition model.

    This function only performs mapping.
    It does not write to PostgreSQL.
    """

    if resource.get("resourceType") != "Condition":
        raise ValueError(
            "Expected a FHIR Condition resource."
        )

    source_condition_id = resource.get("id")

    if not source_condition_id:
        raise ValueError(
            "FHIR Condition resource is missing its id."
        )

    (
        condition_system,
        condition_code,
        condition_display,
    ) = extract_coding(
        resource.get("code")
    )

    clinical_status = None

    clinical_status_data = resource.get(
        "clinicalStatus"
    )

    if isinstance(clinical_status_data, dict):
        _, clinical_status, _ = extract_coding(
            clinical_status_data
        )

    verification_status = None

    verification_status_data = resource.get(
        "verificationStatus"
    )

    if isinstance(verification_status_data, dict):
        _, verification_status, _ = extract_coding(
            verification_status_data
        )

    onset_time = parse_fhir_datetime(
        resource.get("onsetDateTime")
    )

    recorded_time = parse_fhir_datetime(
        resource.get("recordedDate")
    )

    return Condition(
        source_condition_id=source_condition_id,
        patient_id=patient_id,
        encounter_id=encounter_id,
        condition_code=condition_code,
        condition_system=condition_system,
        condition_display=condition_display,
        clinical_status=clinical_status,
        verification_status=verification_status,
        onset_time=onset_time,
        recorded_time=recorded_time,
        source=source,
        source_resource="Condition",
    )