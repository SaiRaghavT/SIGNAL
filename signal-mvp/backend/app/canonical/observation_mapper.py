from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from backend.app.models.observation import Observation


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


def extract_codeable_concept(
    data: dict[str, Any] | None,
) -> tuple[str | None, str | None, str | None]:
    """
    Extract system, code, and display from a
    FHIR CodeableConcept.
    """

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

    return (
        None,
        None,
        data.get("text"),
    )


def map_fhir_observation(
    resource: dict[str, Any],
    patient_id: UUID,
    encounter_id: UUID | None,
    source: str,
) -> Observation:
    """
    Convert a FHIR Observation resource into
    the SIGNAL Observation model.

    This function only performs mapping.
    It does not write to PostgreSQL.
    """

    if resource.get("resourceType") != "Observation":
        raise ValueError(
            "Expected a FHIR Observation resource."
        )

    source_observation_id = resource.get("id")

    if not source_observation_id:
        raise ValueError(
            "FHIR Observation resource is missing its id."
        )

    (
        observation_system,
        observation_code,
        observation_display,
    ) = extract_codeable_concept(
        resource.get("code")
    )

    value_numeric: Decimal | None = None
    value_text: str | None = None
    unit: str | None = None
    value_system: str | None = None
    value_code: str | None = None

    value_quantity = resource.get("valueQuantity")

    if isinstance(value_quantity, dict):

        raw_value = value_quantity.get("value")

        if raw_value is not None:
            try:
                value_numeric = Decimal(str(raw_value))
            except (ValueError, TypeError):
                value_numeric = None

        unit = value_quantity.get("unit")
        value_system = value_quantity.get("system")
        value_code = value_quantity.get("code")

    elif "valueString" in resource:

        value_text = resource.get("valueString")

    elif "valueCodeableConcept" in resource:

        (
            value_system,
            value_code,
            value_text,
        ) = extract_codeable_concept(
            resource.get("valueCodeableConcept")
        )

    elif "valueBoolean" in resource:

        value_text = str(
            resource.get("valueBoolean")
        )

    elif "valueInteger" in resource:

        raw_value = resource.get("valueInteger")

        try:
            value_numeric = Decimal(str(raw_value))
        except (ValueError, TypeError):
            value_numeric = None

    effective_time = parse_fhir_datetime(
        resource.get("effectiveDateTime")
    )

    return Observation(
        source_observation_id=source_observation_id,

        patient_id=patient_id,

        encounter_id=encounter_id,

        observation_code=observation_code,

        observation_system=observation_system,

        observation_display=observation_display,

        status=resource.get("status"),

        value_numeric=value_numeric,

        value_text=value_text,

        unit=unit,

        value_system=value_system,

        value_code=value_code,

        effective_time=effective_time,

        source=source,

        source_resource="Observation",
    )