from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List


# ---------------------------------------------------------
# Structured Trigger Configuration
# ---------------------------------------------------------
#
# These are detection configurations, NOT reportability rules.
#
# A trigger only says:
# "This structured clinical evidence may represent a
# potential public-health reporting candidate."
#
# Jurisdiction and reportability decisions happen downstream.
# ---------------------------------------------------------

STRUCTURED_TRIGGERS: List[Dict[str, Any]] = [
    # Example structure:
    #
    # {
    #     "trigger_id": "example-condition-trigger",
    #     "trigger_type": "CONDITION_CODE",
    #     "resource_type": "Condition",
    #     "code_system": "http://snomed.info/sct",
    #     "codes": ["EXAMPLE_CODE"],
    #     "disease_id": "example-disease",
    # }
]


# ---------------------------------------------------------
# Utility Functions
# ---------------------------------------------------------

def _utc_now() -> str:
    """Return the current UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


def _matches_code(
    resource: Dict[str, Any],
    trigger: Dict[str, Any],
) -> bool:
    """
    Determine whether a normalized clinical resource matches
    a configured structured trigger.
    """

    expected_system = trigger.get("code_system")
    expected_codes = trigger.get("codes", [])

    resource_system = resource.get("system")
    resource_code = resource.get("code")

    if expected_system and resource_system != expected_system:
        return False

    if expected_codes and resource_code not in expected_codes:
        return False

    return True


def _get_resource_list(
    normalized_patient: Dict[str, Any],
    resource_type: str,
) -> List[Dict[str, Any]]:
    """
    Map FHIR resource types to the normalized SIGNAL structure.
    """

    resource_mapping = {
        "Condition": "conditions",
        "Observation": "observations",
        "DiagnosticReport": "diagnostic_reports",
        "MedicationRequest": "medications",
        "Procedure": "procedures",
        "Encounter": "encounters",
    }

    field = resource_mapping.get(resource_type)

    if not field:
        return []

    resources = normalized_patient.get(field, [])

    return resources if isinstance(resources, list) else []


# ---------------------------------------------------------
# Candidate Signal Creation
# ---------------------------------------------------------

def _create_candidate_signal(
    resource: Dict[str, Any],
    trigger: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Create a candidate signal from matched structured evidence.

    This does NOT confirm a reportable case.
    """

    resource_type = trigger.get("resource_type")

    patient_id = resource.get("patient_id")

    signal: Dict[str, Any] = {
        "patient_id": patient_id,
        "encounter_id": resource.get("encounter_id"),
        "trigger_id": trigger.get("trigger_id"),
        "trigger_type": trigger.get("trigger_type"),
        "disease_id": trigger.get("disease_id"),
        "evidence": {
            "source_type": resource_type,
            "source_id": resource.get("id"),
            "code_system": resource.get("system"),
            "code": resource.get("code"),
            "display": resource.get("display"),
        },
        "confidence": 1.0,
        "detected_at": _utc_now(),
    }

    return signal


# ---------------------------------------------------------
# Structured Trigger Detection
# ---------------------------------------------------------

def detect_structured_triggers(
    normalized_patient: Dict[str, Any],
    triggers: List[Dict[str, Any]] | None = None,
) -> List[Dict[str, Any]]:
    """
    Detect potential candidate signals from structured
    clinical information.

    Parameters
    ----------
    normalized_patient:
        SIGNAL normalized patient object produced by the
        FHIR normalization layer.

    triggers:
        Optional trigger configuration. If omitted,
        STRUCTURED_TRIGGERS is used.

    Returns
    -------
    List of candidate signals.

    Important:
        Detection does not determine jurisdiction,
        reportability, or case confirmation.
    """

    if not isinstance(normalized_patient, dict):
        raise ValueError("normalized_patient must be a dictionary.")

    configured_triggers = (
        STRUCTURED_TRIGGERS
        if triggers is None
        else triggers
    )

    candidate_signals: List[Dict[str, Any]] = []

    for trigger in configured_triggers:

        if not isinstance(trigger, dict):
            continue

        resource_type = trigger.get("resource_type")

        if not resource_type:
            continue

        resources = _get_resource_list(
            normalized_patient,
            resource_type,
        )

        for resource in resources:

            if not isinstance(resource, dict):
                continue

            if not _matches_code(resource, trigger):
                continue

            signal = _create_candidate_signal(
                resource,
                trigger,
            )

            candidate_signals.append(signal)

    return candidate_signals