from typing import Any


def canonical_context_to_detection_input(
    context: dict[str, Any],
) -> dict[str, Any]:
    """Adapt SIGNAL canonical data to the detector's normalized shape."""

    patient = context["patient"]
    patient_id = patient["patient_id"]

    # ---------------------------------------------------------
    # Conditions
    # ---------------------------------------------------------
    conditions = []

    for condition in context.get("conditions", []):
        code = condition.get("code") or {}

        conditions.append(
            {
                "id": condition.get("condition_id"),
                "patient_id": condition.get("patient_id", patient_id),
                "encounter_id": condition.get("encounter_id"),
                "system": code.get("system"),
                "code": code.get("code"),
                "display": code.get("display"),
                "status": condition.get("clinical_status"),
            }
        )

    # ---------------------------------------------------------
    # Observations
    # ---------------------------------------------------------
    observations = []

    for observation in context.get("observations", []):
        code = observation.get("code") or {}

        observations.append(
            {
                "id": observation.get("observation_id"),
                "patient_id": observation.get(
                    "patient_id",
                    patient_id,
                ),
                "encounter_id": observation.get("encounter_id"),
                "system": code.get("system"),
                "code": code.get("code"),
                "display": code.get("display"),
                "value": observation.get("value"),
                "status": observation.get("status"),
            }
        )

    # ---------------------------------------------------------
    # Diagnostic Reports / Lab Results
    # ---------------------------------------------------------
    #
    # Lab results are represented as diagnostic_reports for the
    # detector. The linked lab observations are preserved so
    # structured lab triggers can inspect the actual test result.
    #
    # Example:
    #
    # Lab Result
    #   ├── test
    #   ├── conclusion
    #   ├── status
    #   └── observations
    #         ├── code
    #         ├── display
    #         └── value
    #
    # ---------------------------------------------------------
    diagnostic_reports = []

    for lab_result in context.get("lab_results", []):
        test = lab_result.get("test") or {}

        diagnostic_reports.append(
            {
                "id": lab_result.get("lab_result_id"),
                "patient_id": lab_result.get(
                    "patient_id",
                    patient_id,
                ),
                "encounter_id": lab_result.get("encounter_id"),
                "system": test.get("system"),
                "code": test.get("code"),
                "display": test.get("display"),
                "conclusion": lab_result.get("conclusion"),
                "status": lab_result.get("report_status"),
                "observations": lab_result.get(
                    "observations",
                    [],
                ),
            }
        )

    # ---------------------------------------------------------
    # Encounters
    # ---------------------------------------------------------
    encounters = [
        {
            "id": encounter.get("encounter_id"),
            "patient_id": encounter.get(
                "patient_id",
                patient_id,
            ),
            "type": encounter.get("encounter_type"),
            "status": encounter.get("status"),
            "start_time": encounter.get("start_time"),
            "end_time": encounter.get("end_time"),
        }
        for encounter in context.get("encounters", [])
    ]

    # ---------------------------------------------------------
    # Final normalized detection input
    # ---------------------------------------------------------
    return {
        "patient": {
            **patient,
            "id": patient_id,
        },
        "conditions": conditions,
        "observations": observations,
        "diagnostic_reports": diagnostic_reports,
        "medications": [],
        "procedures": [],
        "encounters": encounters,
    }