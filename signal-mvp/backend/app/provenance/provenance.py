from typing import Any


# Mapping between canonical entity types and their
# source-specific identifier field.
SOURCE_ID_FIELDS = {
    "Patient": "source_patient_id",
    "Encounter": "source_encounter_id",
    "Condition": "source_condition_id",
    "Observation": "source_observation_id",
    "LabResult": "source_lab_result_id",
    "ClinicalDocument": "source_document_id",
}


def get_provenance(
    entity: Any,
    entity_type: str,
) -> dict[str, Any]:
    """
    Extract provenance information from a canonical SIGNAL entity.

    Parameters
    ----------
    entity:
        SQLAlchemy canonical model instance.

    entity_type:
        Canonical entity type, for example:
        Patient
        Encounter
        Condition
        Observation
        LabResult
        ClinicalDocument

    Returns
    -------
    dict
        Standardized provenance information.
    """

    if entity_type not in SOURCE_ID_FIELDS:
        raise ValueError(
            f"Unsupported provenance entity type: {entity_type}"
        )

    source_id_field = SOURCE_ID_FIELDS[entity_type]

    source_id = getattr(
        entity,
        source_id_field,
        None,
    )

    source = getattr(
        entity,
        "source",
        None,
    )

    source_resource = getattr(
        entity,
        "source_resource",
        None,
    )

    return {
        "entity_type": entity_type,
        "source": source,
        "source_id": source_id,
        "source_resource": source_resource,
    }