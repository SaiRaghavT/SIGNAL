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
#
# Important:
# - Condition triggers operate on canonical Condition data.
# - LabResult triggers operate on canonical LabResult data.
# - These triggers do NOT determine final reportability.
# ---------------------------------------------------------

STRUCTURED_TRIGGERS: List[Dict[str, Any]] = [
    # -----------------------------------------------------
    # Measles condition — SNOMED CT
    # -----------------------------------------------------
    {
        "trigger_id": "measles-snomed-condition",
        "trigger_type": "CONDITION_CODE",
        "resource_type": "Condition",
        "code_system": "http://snomed.info/sct",
        "codes": [
            "14168008",
            "14189004",
        ],
        "disease_id": "measles",
    },

    # -----------------------------------------------------
    # Measles condition — ICD-10-CM
    # -----------------------------------------------------
    {
        "trigger_id": "measles-icd10cm-condition",
        "trigger_type": "CONDITION_CODE",
        "resource_type": "Condition",
        "code_system": "http://hl7.org/fhir/sid/icd-10-cm",
        "codes": [
            "B05",
            "B05.0",
            "B05.1",
            "B05.2",
            "B05.3",
            "B05.4",
            "B05.81",
            "B05.89",
            "B05.9",
        ],
        "disease_id": "measles",
    },

    # -----------------------------------------------------
    # Measles IgM laboratory result
    # -----------------------------------------------------
    #
    # Canonical SIGNAL LabResult structure:
    #
    # {
    #     "test": {
    #         "system": "http://loinc.org",
    #         "code": "5195-3",
    #         "display": "Measles virus IgM Ab [Presence] in Serum"
    #     },
    #     "report_status": "final",
    #     "conclusion": "Positive for measles IgM"
    # }
    #
    # This is a DETECTION trigger only.
    # It does not independently determine reportability.
    # -----------------------------------------------------
    {
        "trigger_id": "measles-igm-positive-lab",
        "trigger_type": "LAB_RESULT",
        "resource_type": "LabResult",
        "code_system": "http://loinc.org",
        "codes": [
            "5195-3",
        ],
        "disease_id": "measles",
    },
]


# ---------------------------------------------------------
# Utility Functions
# ---------------------------------------------------------

def _utc_now() -> str:
    """Return the current UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


def _get_resource_list(
    normalized_patient: Dict[str, Any],
    resource_type: str,
) -> List[Dict[str, Any]]:
    """
    Map canonical SIGNAL resource types to the corresponding
    normalized patient collections.
    """

    resource_mapping = {
        "Condition": "conditions",
        "Observation": "observations",
        "LabResult": "lab_results",
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


def _get_resource_code_data(
    resource: Dict[str, Any],
    resource_type: str,
) -> tuple[str | None, str | None, str | None]:
    """
    Extract terminology information from a normalized SIGNAL
    resource.

    Most structured resources expose:

        system
        code
        display

    Canonical LabResult exposes terminology under:

        test.system
        test.code
        test.display
    """

    if resource_type == "LabResult":
        test = resource.get("test")

        if not isinstance(test, dict):
            return None, None, None

        return (
            test.get("system"),
            test.get("code"),
            test.get("display"),
        )

    return (
        resource.get("system"),
        resource.get("code"),
        resource.get("display"),
    )


def _matches_code(
    resource: Dict[str, Any],
    trigger: Dict[str, Any],
) -> bool:
    """
    Determine whether a normalized clinical resource matches
    a configured structured trigger.
    """

    resource_type = trigger.get("resource_type")

    expected_system = trigger.get("code_system")
    expected_codes = trigger.get("codes", [])

    resource_system, resource_code, _ = _get_resource_code_data(
        resource,
        resource_type,
    )

    # If a trigger specifies a terminology system, it must match.
    if expected_system and resource_system != expected_system:
        return False

    # If a trigger specifies codes, the resource code must match.
    if expected_codes and resource_code not in expected_codes:
        return False

    return True


def _get_source_id(
    resource: Dict[str, Any],
    resource_type: str,
) -> str | None:
    """
    Return the best source identifier for the evidence.

    Canonical resources normally use `id`.

    Canonical LabResult uses:
        source_lab_result_id
        lab_result_id
    """

    if resource_type == "LabResult":
        return (
            resource.get("source_lab_result_id")
            or resource.get("lab_result_id")
            or resource.get("id")
        )

    return resource.get("id")


def _get_lab_result_status(
    resource: Dict[str, Any],
) -> str | None:
    """
    Return the canonical laboratory report status.
    """

    status = resource.get("report_status")

    if status is None:
        return None

    return str(status)


def _is_positive_lab_result(
    resource: Dict[str, Any],
) -> bool:
    """
    Determine whether a canonical LabResult contains positive
    evidence.

    This function is intentionally conservative.

    A positive result is recognized from the canonical
    `conclusion` text.

    If no conclusion is available, the result is not treated
    as positive by this helper.
    """

    conclusion = resource.get("conclusion")

    if conclusion is None:
        return False

    if not isinstance(conclusion, str):
        return False

    normalized = conclusion.strip().lower()

    positive_terms = (
        "positive",
        "detected",
        "reactive",
        "present",
    )

    return any(term in normalized for term in positive_terms)


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

    (
        code_system,
        code,
        display,
    ) = _get_resource_code_data(
        resource,
        resource_type,
    )

    source_id = _get_source_id(
        resource,
        resource_type,
    )

    evidence: Dict[str, Any] = {
        "source_type": resource_type,
        "source_id": source_id,
        "code_system": code_system,
        "code": code,
        "display": display,
    }

    # Add laboratory-specific evidence without changing
    # the structure of non-lab signals.
    if resource_type == "LabResult":
        evidence["report_status"] = _get_lab_result_status(resource)
        evidence["conclusion"] = resource.get("conclusion")
        evidence["positive"] = _is_positive_lab_result(resource)

    signal: Dict[str, Any] = {
        "patient_id": patient_id,
        "encounter_id": resource.get("encounter_id"),
        "trigger_id": trigger.get("trigger_id"),
        "trigger_type": trigger.get("trigger_type"),
        "disease_id": trigger.get("disease_id"),
        "evidence": evidence,
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
        canonical/FHIR normalization layer.

    triggers:
        Optional trigger configuration. If omitted,
        STRUCTURED_TRIGGERS is used.

    Returns
    -------
    List[Dict[str, Any]]
        Detected candidate signals.

    Important
    ---------
    Detection does not determine jurisdiction,
    reportability, or case confirmation.
    """

    if not isinstance(normalized_patient, dict):
        raise ValueError(
            "normalized_patient must be a dictionary."
        )

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

            if not _matches_code(
                resource,
                trigger,
            ):
                continue

            # For LabResult triggers, require an explicitly
            # positive result.
            #
            # This prevents every measles IgM test order/result
            # from automatically becoming a positive signal.
            if resource_type == "LabResult":
                if not _is_positive_lab_result(resource):
                    continue

            signal = _create_candidate_signal(
                resource,
                trigger,
            )

            candidate_signals.append(signal)

    return candidate_signals