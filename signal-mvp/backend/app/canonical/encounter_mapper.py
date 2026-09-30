from datetime import datetime
from typing import Any
from uuid import UUID

from backend.app.models.encounter import Encounter


def parse_fhir_datetime(value: str | None) -> datetime | None:
    """
    Convert a FHIR dateTime string into a Python datetime.
    """
    if not value:
        return None

    try:
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def map_fhir_encounter(
    resource: dict[str, Any],
    patient_id: UUID,
    source: str,
) -> Encounter:
    """
    Convert a FHIR Encounter resource into
    the SIGNAL Encounter model.

    This function only performs mapping.
    It does not write to PostgreSQL.
    """

    if resource.get("resourceType") != "Encounter":
        raise ValueError(
            "Expected a FHIR Encounter resource."
        )

    source_encounter_id = resource.get("id")

    if not source_encounter_id:
        raise ValueError(
            "FHIR Encounter resource is missing its id."
        )

    encounter_period = resource.get("period") or {}

    encounter_type = None

    types = resource.get("class")

    if isinstance(types, dict):
        encounter_type = (
            types.get("display")
            or types.get("code")
        )

    if not encounter_type:
        encounter_types = resource.get("type") or []

        if encounter_types:
            first_type = encounter_types[0]

            if isinstance(first_type, dict):
                coding = first_type.get("coding") or []

                if coding:
                    encounter_type = (
                        coding[0].get("display")
                        or coding[0].get("code")
                    )

    service_provider = resource.get(
        "serviceProvider"
    )

    facility_id = None

    if isinstance(service_provider, dict):
        facility_id = service_provider.get("reference")

    return Encounter(
        source_encounter_id=source_encounter_id,

        patient_id=patient_id,

        facility_id=facility_id,

        encounter_type=encounter_type,

        status=resource.get("status"),

        start_time=parse_fhir_datetime(
            encounter_period.get("start")
        ),

        end_time=parse_fhir_datetime(
            encounter_period.get("end")
        ),

        source=source,

        source_resource="Encounter",
    )