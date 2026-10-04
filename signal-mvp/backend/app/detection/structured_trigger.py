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
    {
        "trigger_id": "measles-snomed-condition",
        "trigger_type": "CONDITION_CODE",
        "resource_type": "Condition",
        "code_system": "http://snomed.info/sct",
        "codes": ["14168008", "14189004"],
        "disease_id": "measles",
    },
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
    {
        "trigger_id": "measles-pcr-positive-lab",
        "trigger_type": "LAB_RESULT",
        "resource_type": "DiagnosticReport",
        "disease_id": "measles",
        "test_terms": [
            "measles pcr",
            "measles polymerase chain reaction",
            "rubeola pcr",
        ],
        "positive_terms": [
            "positive",
            "detected",
        ],
    },
    {
        "trigger_id": "measles-igm-positive-lab",
        "trigger_type": "LAB_RESULT",
        "resource_type": "DiagnosticReport",
        "disease_id": "measles",
        "test_terms": [
            "measles igm",
            "measles immunoglobulin m",
            "rubeola igm",
        ],
        "positive_terms": [
            "positive",
            "reactive",
        ],
    },
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
    a configured structured code trigger.
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
    Map resource types to the normalized SIGNAL structure.
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


def _normalize_text(value: Any) -> str:
    """Convert a value to normalized lowercase text."""

    if value is None:
        return ""

    return str(value).strip().lower()


# ---------------------------------------------------------
# Lab Trigger Helpers
# ---------------------------------------------------------

def _lab_test_matches(
    resource: Dict[str, Any],
    trigger: Dict[str, Any],
) -> bool:
    """
    Determine whether the diagnostic report represents
    the configured measles laboratory test.
    """

    test_terms = trigger.get("test_terms", [])

    test_code = _normalize_text(resource.get("code"))
    test_display = _normalize_text(resource.get("display"))
    conclusion = _normalize_text(resource.get("conclusion"))

    searchable_text = " ".join(
        value
        for value in [
            test_code,
            test_display,
            conclusion,
        ]
        if value
    )

    return any(
        term.lower() in searchable_text
        for term in test_terms
    )


def _get_lab_observations(
    resource: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Return linked observations from a diagnostic report.
    """

    observations = resource.get("observations", [])

    return (
        observations
        if isinstance(observations, list)
        else []
    )


def _lab_result_is_positive(
    resource: Dict[str, Any],
    trigger: Dict[str, Any],
) -> bool:
    """
    Determine whether a measles laboratory result is positive.

    Positive evidence can come from:
    - linked observation value_text
    - linked observation value_code
    - diagnostic report conclusion

    Negative results such as "negative" or "not detected"
    do not trigger a candidate signal.
    """

    positive_terms = [
        term.lower()
        for term in trigger.get("positive_terms", [])
    ]

    evidence_values: List[str] = []

    conclusion = resource.get("conclusion")

    if conclusion:
        evidence_values.append(
            _normalize_text(conclusion)
        )

    for observation in _get_lab_observations(resource):
        if not isinstance(observation, dict):
            continue

        value = observation.get("value")

        if isinstance(value, dict):
            for key in (
                "text",
                "code",
            ):
                value_part = value.get(key)

                if value_part is not None:
                    evidence_values.append(
                        _normalize_text(value_part)
                    )

        elif value is not None:
            evidence_values.append(
                _normalize_text(value)
            )

    return any(
        any(
            positive_term in evidence
            for positive_term in positive_terms
        )
        for evidence in evidence_values
    )


def _matches_lab_trigger(
    resource: Dict[str, Any],
    trigger: Dict[str, Any],
) -> bool:
    """
    Determine whether a diagnostic report represents
    a positive configured measles laboratory result.
    """

    if not _lab_test_matches(resource, trigger):
        return False

    if not _lab_result_is_positive(resource, trigger):
        return False

    return True


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


def _create_lab_candidate_signal(
    resource: Dict[str, Any],
    trigger: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Create a candidate signal from a positive laboratory result.
    """

    observations = _get_lab_observations(resource)

    observation_evidence = []

    for observation in observations:
        if not isinstance(observation, dict):
            continue

        observation_evidence.append(
            {
                "id": observation.get("observation_id"),
                "code": observation.get("code"),
                "display": observation.get("display"),
                "value": observation.get("value"),
                "status": observation.get("status"),
            }
        )

    return {
        "patient_id": resource.get("patient_id"),
        "encounter_id": resource.get("encounter_id"),
        "trigger_id": trigger.get("trigger_id"),
        "trigger_type": "LAB_RESULT",
        "disease_id": trigger.get("disease_id"),
        "evidence": {
            "source_type": "DiagnosticReport",
            "source_id": resource.get("id"),
            "code_system": resource.get("system"),
            "code": resource.get("code"),
            "display": resource.get("display"),
            "conclusion": resource.get("conclusion"),
            "observations": observation_evidence,
        },
        "confidence": 1.0,
        "detected_at": _utc_now(),
    }


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

    This includes:
    - Condition-based triggers
    - Laboratory-result triggers

    Parameters
    ----------
    normalized_patient:
        SIGNAL normalized patient object.

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

            # ---------------------------------------------
            # Laboratory trigger
            # ---------------------------------------------
            if trigger.get("trigger_type") == "LAB_RESULT":
                if not _matches_lab_trigger(
                    resource,
                    trigger,
                ):
                    continue

                signal = _create_lab_candidate_signal(
                    resource,
                    trigger,
                )

                candidate_signals.append(signal)
                continue

            # ---------------------------------------------
            # Existing structured code trigger
            # ---------------------------------------------
            if not _matches_code(resource, trigger):
                continue

            signal = _create_candidate_signal(
                resource,
                trigger,
            )

            candidate_signals.append(signal)

    return candidate_signals