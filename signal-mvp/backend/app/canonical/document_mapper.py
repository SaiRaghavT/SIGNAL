from datetime import datetime
from typing import Any
from uuid import UUID

from backend.app.models.clinical_document import ClinicalDocument


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
    Extract system, code, and display from
    a FHIR CodeableConcept.
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


def extract_attachment(
    resource: dict[str, Any],
) -> tuple[str | None, str | None, str | None]:
    """
    Extract basic information from the first
    DocumentReference.content[].attachment.

    Returns:
        content_type,
        content_location,
        extracted_text
    """

    contents = resource.get("content") or []

    if not contents:
        return None, None, None

    first_content = contents[0]

    if not isinstance(first_content, dict):
        return None, None, None

    attachment = first_content.get("attachment")

    if not isinstance(attachment, dict):
        return None, None, None

    content_type = attachment.get("contentType")

    content_location = (
        attachment.get("url")
        or attachment.get("data")
    )

    # We do not decode or extract document text here.
    # Document Intelligence will handle that later.
    extracted_text = None

    return (
        content_type,
        content_location,
        extracted_text,
    )


def map_fhir_document_reference(
    resource: dict[str, Any],
    patient_id: UUID,
    encounter_id: UUID | None,
    source: str,
) -> ClinicalDocument:
    """
    Convert a FHIR DocumentReference resource into
    the SIGNAL ClinicalDocument model.

    This function only performs mapping.
    It does not write to PostgreSQL.
    """

    if resource.get("resourceType") != "DocumentReference":
        raise ValueError(
            "Expected a FHIR DocumentReference resource."
        )

    source_document_id = resource.get("id")

    if not source_document_id:
        raise ValueError(
            "FHIR DocumentReference resource is missing its id."
        )

    document_type = None

    type_data = resource.get("type")

    if isinstance(type_data, dict):
        (
            _,
            type_code,
            type_display,
        ) = extract_codeable_concept(type_data)

        document_type = (
            type_display
            or type_code
        )

    content_type = None
    content_location = None
    extracted_text = None

    (
        content_type,
        content_location,
        extracted_text,
    ) = extract_attachment(resource)

    return ClinicalDocument(
        source_document_id=source_document_id,

        patient_id=patient_id,

        encounter_id=encounter_id,

        document_type=document_type,

        document_status=resource.get("status"),

        title=resource.get("description"),

        document_date=parse_fhir_datetime(
            resource.get("date")
        ),

        author_reference=(
            resource.get("author", [{}])[0].get("reference")
            if resource.get("author")
            and isinstance(resource.get("author"), list)
            and isinstance(resource.get("author")[0], dict)
            else None
        ),

        content_type=content_type,

        content_location=content_location,

        extracted_text=extracted_text,

        source=source,

        source_resource="DocumentReference",
    )