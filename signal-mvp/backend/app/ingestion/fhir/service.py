from typing import Any

from sqlalchemy.orm import Session

from backend.app.ingestion.fhir.parser import parse_fhir_bundle
from backend.app.ingestion.fhir.validator import validate_fhir_bundle

from backend.app.canonical.patient_mapper import map_fhir_patient
from backend.app.canonical.encounter_mapper import map_fhir_encounter
from backend.app.canonical.condition_mapper import map_fhir_condition
from backend.app.canonical.observation_mapper import map_fhir_observation
from backend.app.canonical.lab_result_mapper import (
    map_fhir_diagnostic_report,
)
from backend.app.canonical.document_mapper import (
    map_fhir_document_reference,
)

from backend.app.canonical.persistence import (
    save_patient,
    save_encounter,
    save_condition,
    save_observation,
    save_lab_result,
    save_clinical_document,
)

from backend.app.quality.fhir_quality import (
    validate_fhir_data_quality,
)


def _get_reference_id(
    reference_data: dict[str, Any] | None,
    resource_type: str,
) -> str | None:
    """
    Extract a source resource ID from a FHIR reference.

    Supported formats:

        Patient/123
        urn:uuid:123
        https://example.org/fhir/Patient/123
    """

    if not isinstance(reference_data, dict):
        return None

    reference = reference_data.get("reference")

    if not isinstance(reference, str):
        return None

    reference = reference.strip()

    if not reference:
        return None

    # ---------------------------------------------------------
    # Relative FHIR reference
    # Example:
    # Patient/123
    # ---------------------------------------------------------

    prefix = f"{resource_type}/"

    if reference.startswith(prefix):
        return reference[len(prefix):]

    # ---------------------------------------------------------
    # Bundle-local UUID reference
    # Example:
    # urn:uuid:123
    # ---------------------------------------------------------

    urn_prefix = "urn:uuid:"

    if reference.startswith(urn_prefix):
        return reference[len(urn_prefix):]

    # ---------------------------------------------------------
    # Absolute FHIR reference
    # Example:
    # https://example.org/fhir/Patient/123
    # ---------------------------------------------------------

    marker = f"/{resource_type}/"

    if marker in reference:
        return reference.rsplit(marker, 1)[1]

    return None


def ingest_fhir_bundle(
    db: Session,
    payload: dict[str, Any],
    source: str = "synthea",
) -> dict[str, Any]:
    """
    Ingest a FHIR Bundle into the SIGNAL canonical PostgreSQL model.

    Processing flow:

        FHIR Bundle
            ↓
        Structural Validation
            ↓
        Parsing
            ↓
        Data Quality Validation
            ↓
        Patient
            ↓
        Encounter
            ↓
        Condition
            ↓
        Observation
            ↓
        DiagnosticReport → LabResult
            ↓
        DocumentReference → ClinicalDocument
            ↓
        PostgreSQL

    The complete Bundle is processed inside one database transaction.

    If any resource fails:
        ROLLBACK

    If the complete Bundle succeeds:
        COMMIT
    """

    # =========================================================
    # 1. Validate FHIR Bundle structure
    # =========================================================

    validate_fhir_bundle(payload)

    # =========================================================
    # 2. Parse supported FHIR resources
    # =========================================================

    resources = parse_fhir_bundle(payload)

    # =========================================================
    # 3. Validate FHIR data quality
    # =========================================================

    quality_result = validate_fhir_data_quality(resources)

    if quality_result["status"] == "failed":
        raise ValueError(
            "FHIR data quality validation failed: "
            f"{quality_result['error_count']} errors found."
        )

    # =========================================================
    # 4. Lookup maps
    #
    # These maps translate:
    #
    # FHIR source ID
    #       ↓
    # SIGNAL PostgreSQL UUID
    # =========================================================

    patient_ids: dict[str, Any] = {}
    encounter_ids: dict[str, Any] = {}
    observation_ids: dict[str, Any] = {}

    # =========================================================
    # 5. Ingestion counters
    # =========================================================

    counts = {
        "patients": 0,
        "encounters": 0,
        "conditions": 0,
        "observations": 0,
        "lab_results": 0,
        "clinical_documents": 0,
    }

    try:

        # =====================================================
        # 6. PATIENTS
        # =====================================================

        for resource in resources.get("Patient", []):

            patient = map_fhir_patient(
                resource=resource,
                source=source,
            )

            saved_patient = save_patient(
                db=db,
                patient=patient,
            )

            source_patient_id = resource.get("id")

            if not source_patient_id:
                raise ValueError(
                    "FHIR Patient resource is missing its id."
                )

            patient_ids[source_patient_id] = (
                saved_patient.patient_id
            )

            counts["patients"] += 1

        # =====================================================
        # 7. ENCOUNTERS
        # =====================================================

        for resource in resources.get("Encounter", []):

            source_encounter_id = resource.get("id")

            if not source_encounter_id:
                raise ValueError(
                    "FHIR Encounter resource is missing its id."
                )

            patient_source_id = _get_reference_id(
                resource.get("subject"),
                "Patient",
            )

            if not patient_source_id:
                raise ValueError(
                    f"Encounter {source_encounter_id} "
                    "does not contain a valid Patient reference."
                )

            patient_id = patient_ids.get(
                patient_source_id
            )

            if patient_id is None:
                raise ValueError(
                    f"Encounter {source_encounter_id} "
                    f"references unknown Patient/"
                    f"{patient_source_id}."
                )

            encounter = map_fhir_encounter(
                resource=resource,
                patient_id=patient_id,
                source=source,
            )

            saved_encounter = save_encounter(
                db=db,
                encounter=encounter,
            )

            encounter_ids[source_encounter_id] = (
                saved_encounter.encounter_id
            )

            counts["encounters"] += 1

        # =====================================================
        # 8. CONDITIONS
        # =====================================================

        for resource in resources.get("Condition", []):

            source_condition_id = resource.get("id")

            if not source_condition_id:
                raise ValueError(
                    "FHIR Condition resource is missing its id."
                )

            # -------------------------------------------------
            # Patient reference
            # -------------------------------------------------

            patient_source_id = _get_reference_id(
                resource.get("subject"),
                "Patient",
            )

            if not patient_source_id:
                raise ValueError(
                    f"Condition {source_condition_id} "
                    "does not contain a valid Patient reference."
                )

            patient_id = patient_ids.get(
                patient_source_id
            )

            if patient_id is None:
                raise ValueError(
                    f"Condition {source_condition_id} "
                    f"references unknown Patient/"
                    f"{patient_source_id}."
                )

            # -------------------------------------------------
            # Encounter reference
            # -------------------------------------------------

            encounter_source_id = _get_reference_id(
                resource.get("encounter"),
                "Encounter",
            )

            encounter_id = None

            if encounter_source_id:

                encounter_id = encounter_ids.get(
                    encounter_source_id
                )

                if encounter_id is None:
                    raise ValueError(
                        f"Condition {source_condition_id} "
                        f"references unknown Encounter/"
                        f"{encounter_source_id}."
                    )

            condition = map_fhir_condition(
                resource=resource,
                patient_id=patient_id,
                encounter_id=encounter_id,
                source=source,
            )

            save_condition(
                db=db,
                condition=condition,
            )

            counts["conditions"] += 1

        # =====================================================
        # 9. OBSERVATIONS
        # =====================================================

        for resource in resources.get("Observation", []):

            source_observation_id = resource.get("id")

            if not source_observation_id:
                raise ValueError(
                    "FHIR Observation resource is missing its id."
                )

            # -------------------------------------------------
            # Patient reference
            # -------------------------------------------------

            patient_source_id = _get_reference_id(
                resource.get("subject"),
                "Patient",
            )

            if not patient_source_id:
                raise ValueError(
                    f"Observation {source_observation_id} "
                    "does not contain a valid Patient reference."
                )

            patient_id = patient_ids.get(
                patient_source_id
            )

            if patient_id is None:
                raise ValueError(
                    f"Observation {source_observation_id} "
                    f"references unknown Patient/"
                    f"{patient_source_id}."
                )

            # -------------------------------------------------
            # Encounter reference
            # -------------------------------------------------

            encounter_source_id = _get_reference_id(
                resource.get("encounter"),
                "Encounter",
            )

            encounter_id = None

            if encounter_source_id:

                encounter_id = encounter_ids.get(
                    encounter_source_id
                )

                if encounter_id is None:
                    raise ValueError(
                        f"Observation {source_observation_id} "
                        f"references unknown Encounter/"
                        f"{encounter_source_id}."
                    )

            observation = map_fhir_observation(
                resource=resource,
                patient_id=patient_id,
                encounter_id=encounter_id,
                source=source,
            )

            saved_observation = save_observation(
                db=db,
                observation=observation,
            )

            observation_ids[source_observation_id] = (
                saved_observation.observation_id
            )

            counts["observations"] += 1

        # =====================================================
        # 10. DIAGNOSTIC REPORTS → LAB RESULTS
        # =====================================================

        for resource in resources.get(
            "DiagnosticReport",
            [],
        ):

            source_lab_result_id = resource.get("id")

            if not source_lab_result_id:
                raise ValueError(
                    "FHIR DiagnosticReport resource "
                    "is missing its id."
                )

            # -------------------------------------------------
            # Patient reference
            # -------------------------------------------------

            patient_source_id = _get_reference_id(
                resource.get("subject"),
                "Patient",
            )

            if not patient_source_id:
                raise ValueError(
                    f"DiagnosticReport "
                    f"{source_lab_result_id} "
                    "does not contain a valid Patient reference."
                )

            patient_id = patient_ids.get(
                patient_source_id
            )

            if patient_id is None:
                raise ValueError(
                    f"DiagnosticReport "
                    f"{source_lab_result_id} "
                    f"references unknown Patient/"
                    f"{patient_source_id}."
                )

            # -------------------------------------------------
            # Encounter reference
            # -------------------------------------------------

            encounter_source_id = _get_reference_id(
                resource.get("encounter"),
                "Encounter",
            )

            encounter_id = None

            if encounter_source_id:

                encounter_id = encounter_ids.get(
                    encounter_source_id
                )

                if encounter_id is None:
                    raise ValueError(
                        f"DiagnosticReport "
                        f"{source_lab_result_id} "
                        f"references unknown Encounter/"
                        f"{encounter_source_id}."
                    )

            # -------------------------------------------------
            # Map DiagnosticReport
            # -------------------------------------------------

            lab_result, observation_source_ids = (
                map_fhir_diagnostic_report(
                    resource=resource,
                    patient_id=patient_id,
                    encounter_id=encounter_id,
                    source=source,
                )
            )

            # -------------------------------------------------
            # Persist LabResult and Observation links
            # -------------------------------------------------

            save_lab_result(
                db=db,
                lab_result=lab_result,
                observation_source_ids=observation_source_ids,
            )

            counts["lab_results"] += 1

        # =====================================================
        # 11. DOCUMENT REFERENCES
        # =====================================================

        for resource in resources.get(
            "DocumentReference",
            [],
        ):

            source_document_id = resource.get("id")

            if not source_document_id:
                raise ValueError(
                    "FHIR DocumentReference resource "
                    "is missing its id."
                )

            # -------------------------------------------------
            # Patient reference
            # -------------------------------------------------

            patient_source_id = _get_reference_id(
                resource.get("subject"),
                "Patient",
            )

            if not patient_source_id:
                raise ValueError(
                    f"DocumentReference "
                    f"{source_document_id} "
                    "does not contain a valid Patient reference."
                )

            patient_id = patient_ids.get(
                patient_source_id
            )

            if patient_id is None:
                raise ValueError(
                    f"DocumentReference "
                    f"{source_document_id} "
                    f"references unknown Patient/"
                    f"{patient_source_id}."
                )

            # -------------------------------------------------
            # Encounter reference
            #
            # DocumentReference uses:
            #
            # context.encounter[]
            # -------------------------------------------------

            encounter_id = None

            context = resource.get("context")

            if isinstance(context, dict):

                encounter_references = (
                    context.get("encounter") or []
                )

                if encounter_references:

                    encounter_source_id = _get_reference_id(
                        encounter_references[0],
                        "Encounter",
                    )

                    if encounter_source_id:

                        encounter_id = encounter_ids.get(
                            encounter_source_id
                        )

                        if encounter_id is None:
                            raise ValueError(
                                f"DocumentReference "
                                f"{source_document_id} "
                                f"references unknown Encounter/"
                                f"{encounter_source_id}."
                            )

            document = map_fhir_document_reference(
                resource=resource,
                patient_id=patient_id,
                encounter_id=encounter_id,
                source=source,
            )

            save_clinical_document(
                db=db,
                document=document,
            )

            counts["clinical_documents"] += 1

        # =====================================================
        # 12. COMMIT COMPLETE BUNDLE
        # =====================================================

        db.commit()

    except Exception:

        # -----------------------------------------------------
        # If anything fails, rollback the entire Bundle.
        # -----------------------------------------------------

        db.rollback()
        raise

    # =========================================================
    # 13. Return ingestion result
    # =========================================================

    return {
        "status": "success",
        "source": source,
        "resource_type": payload.get("resourceType"),
        "counts": counts,
        "total_canonical_records": sum(counts.values()),
        "quality": {
            "status": quality_result["status"],
            "error_count": quality_result["error_count"],
            "warning_count": quality_result["warning_count"],
            "issue_count": quality_result["issue_count"],
        },
    }