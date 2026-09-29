from datetime import date
from typing import Any

from backend.app.models.patient import Patient


def parse_fhir_date(value: str | None) -> date | None:
    """
    Convert a FHIR date string (YYYY-MM-DD) to a Python date.
    """
    if not value:
        return None

    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def map_fhir_patient(
    resource: dict[str, Any],
    source: str,
) -> Patient:
    """
    Convert a FHIR Patient resource into the SIGNAL Patient model.

    This function only performs mapping.
    It does not write to PostgreSQL.
    """

    if resource.get("resourceType") != "Patient":
        raise ValueError(
            "Expected a FHIR Patient resource."
        )

    source_patient_id = resource.get("id")

    if not source_patient_id:
        raise ValueError(
            "FHIR Patient resource is missing its id."
        )

    address = resource.get("address") or []
    primary_address = address[0] if address else {}

    return Patient(
        source_patient_id=source_patient_id,

        date_of_birth=parse_fhir_date(
            resource.get("birthDate")
        ),

        sex=resource.get("gender"),

        address_line=(
            " ".join(primary_address.get("line", []))
            if primary_address.get("line")
            else None
        ),

        city=primary_address.get("city"),

        county=primary_address.get("district"),

        state=primary_address.get("state"),

        postal_code=primary_address.get("postalCode"),

        source=source,

        source_resource="Patient",
    )