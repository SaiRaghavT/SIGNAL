from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.app.detection.disease_concepts import canonical_disease_id

from .trigger_loader import (
    build_trigger_code_index,
    find_value_sets_containing_code,
    get_value_sets,
    match_trigger_code,
)


# =========================================================
# Backward compatibility
# =========================================================

STRUCTURED_TRIGGERS = {}
_MEASLES_LAB_TEST_VALUE_SET_URL = "http://cts.nlm.nih.gov/fhir/ValueSet/2.16.840.1.113762.1.4.1146.297"


# =========================================================
# Utility
# =========================================================


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_resource_list(
    normalized_patient: Dict[str, Any],
    resource_type: str,
) -> List[Dict[str, Any]]:
    """
    Resolve canonical SIGNAL resources.

    Supports both:

        diagnostic_reports

    and:

        lab_results

    for laboratory data.
    """

    mapping = {
        "Condition": "conditions",
        "Observation": "observations",

        # Support both canonical lab field names.
        "DiagnosticReport": ("diagnostic_reports", "lab_results"),

        "MedicationRequest": "medications",
        "Procedure": "procedures",
        "Encounter": "encounters",

        # Clinical documents are handled separately.
        "ClinicalDocument": "clinical_documents",
    }

    field = mapping.get(resource_type)

    if not field:
        return []

    if isinstance(field, tuple):
        resources = []
        for candidate_field in field:
            values = normalized_patient.get(candidate_field, [])
            if isinstance(values, list):
                resources.extend(values)
        return resources

    resources = normalized_patient.get(field, [])
    if resource_type == "DiagnosticReport" and not resources:
        resources = normalized_patient.get("diagnostic_reports", [])

    return (
        resources
        if isinstance(resources, list)
        else []
    )


def _normalize_code_system(
    system: Optional[str],
) -> Optional[str]:
    """Normalize common coding aliases to their canonical FHIR systems."""

    if not isinstance(system, str):
        return system

    normalized = system.strip()
    if not normalized:
        return None

    aliases = {
        "LN": "http://loinc.org",
        "LOINC": "http://loinc.org",
        "SCT": "http://snomed.info/sct",
        "SNOMED": "http://snomed.info/sct",
        "SNOMED-CT": "http://snomed.info/sct",
        "RXNORM": "http://www.nlm.nih.gov/research/umls/rxnorm",
        "CVX": "http://hl7.org/fhir/sid/cvx",
    }

    return aliases.get(normalized.upper(), normalized)


def _extract_code(
    resource: Dict[str, Any],
) -> tuple[
    Optional[str],
    Optional[str],
    Optional[str],
]:
    """
    Extract system, code and display.

    Supports nested and flattened coding.
    """

    code = resource.get("code")

    if isinstance(code, dict):
        return (
            _normalize_code_system(code.get("system")),
            code.get("code"),
            code.get("display"),
        )

    return (
        _normalize_code_system(resource.get("system")),
        code,
        resource.get("display"),
    )


def _resource_id(
    resource: Dict[str, Any],
) -> Optional[str]:
    """
    Resolve the source resource identifier.
    """

    return (
        resource.get("id")
        or resource.get("resource_id")
        or resource.get("condition_id")
        or resource.get("observation_id")
        or resource.get("lab_result_id")
        or resource.get("diagnostic_report_id")
        or resource.get("document_id")
        or resource.get("source_document_id")
        or resource.get("medication_id")
        or resource.get("procedure_id")
        or resource.get("encounter_id")
    )


def _build_trigger_key(
    system: Optional[str],
    code: Optional[str],
) -> Optional[str]:
    """
    Stable identity for the actual coded clinical trigger.
    """

    if not system or code is None:
        return None

    return f"{system}|{code}"


def _resolve_trigger_concept_key(
    match: Dict[str, Any],
) -> Optional[str]:
    """
    Resolve the stable clinical concept identity from the
    authoritative eRSD ValueSet metadata.
    """

    if not isinstance(match, dict):
        return None

    value_set_ids = match.get("value_set_ids") or []

    if not isinstance(value_set_ids, list):
        return None

    value_sets = get_value_sets()

    for value_set_id in value_set_ids:
        value_set = value_sets.get(value_set_id)

        if not isinstance(value_set, dict):
            continue

        use_context = (
            value_set.get("useContext")
            or value_set.get("use_context")
            or []
        )

        if isinstance(use_context, dict):
            use_context = [use_context]

        for context in use_context:
            if not isinstance(context, dict):
                continue

            context_code = context.get("code") or {}

            if not isinstance(context_code, dict):
                continue

            if context_code.get("code") != "focus":
                continue

            concept = (
                context.get("valueCodeableConcept")
                or context.get("value_codeable_concept")
                or {}
            )

            if not isinstance(concept, dict):
                continue

            codings = concept.get("coding") or []

            if not isinstance(codings, list):
                continue

            for coding in codings:
                if not isinstance(coding, dict):
                    continue

                system = coding.get("system")
                code = coding.get("code")

                if system and code:
                    return f"{system}|{code}"

    return None
# =========================================================
# RCTC Matching
# =========================================================


def _match_resource_against_rctc(
    resource: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Match a structured clinical code against the
    official eRSD/RCTC bundle.
    """

    system, code, display = _extract_code(
        resource
    )

    if not system or code is None:
        return []

    matches = match_trigger_code(
        system=system,
        code=str(code),
    )

    return [
        {
            **match,
            "resource_system": system,
            "resource_code": str(code),
            "resource_display": display,
        }
        for match in matches
    ]


# =========================================================
# Structured Evidence
# =========================================================


def _create_structured_signal(
    resource: Dict[str, Any],
    match: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Create a normalized structured candidate signal.

    No disease-specific or jurisdiction-specific logic
    is applied here.
    """

    system, code, display = _extract_code(
        resource
    )

    trigger_key = _build_trigger_key(
        system,
        str(code) if code is not None else None,
    )

    return {
        "patient_id": resource.get(
            "patient_id"
        ),

        "encounter_id": resource.get(
            "encounter_id"
        ),

        "trigger_key": trigger_key,

        "trigger_id": match.get(
            "group_id"
        ),

        "trigger_type": match.get(
            "group"
        ),

        "trigger_concept_key": _resolve_trigger_concept_key(match),
        "disease_id": canonical_disease_id(
            _resolve_trigger_concept_key(match) or match.get("disease_id")
        ),
        "evidence": {
            "source_type": resource.get(
                "resource_type",
                resource.get(
                    "resourceType",
                    "structured",
                ),
            ),

            "source_id": _resource_id(
                resource
            ),

            "code_system": system,

            "code": (
                str(code)
                if code is not None
                else None
            ),

            "display": display,

            "rctc_group_id": match.get(
                "group_id"
            ),

            "rctc_group": match.get(
                "group"
            ),

            "value_sets": match.get(
                "value_sets",
                [],
            ),

            "value_set_ids": match.get(
                "value_set_ids",
                [],
            ),

            "value_set_urls": match.get(
                "value_set_urls",
                [],
            ),
        },

        "confidence": 1.0,

        "detected_at": _utc_now(),
    }


# =========================================================
# Laboratory Evidence
# =========================================================


def _get_lab_code_candidates(
    resource: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Extract laboratory test and linked observations.

    SIGNAL canonical lab records use:

        test
        observations
        conclusion
        report_status
    """

    candidates: List[
        Dict[str, Any]
    ] = []

    test = resource.get("test")

    if isinstance(test, dict):

        system = test.get(
            "system"
        )

        code = test.get(
            "code"
        )

        display = test.get(
            "display"
        )

        if system and code is not None:

            candidates.append(
                {
                    **resource,

                    "code": {
                        "system": system,
                        "code": code,
                        "display": display,
                    },

                    "resource_type":
                        "DiagnosticReport",
                }
            )

    else:

        system, code, display = (
            _extract_code(
                resource
            )
        )

        if system and code is not None:

            candidates.append(
                {
                    **resource,

                    "system": system,

                    "code": code,

                    "display": display,

                    "resource_type":
                        "DiagnosticReport",
                }
            )

    observations = resource.get(
        "observations",
        [],
    )

    if isinstance(
        observations,
        list,
    ):

        for observation in observations:

            if not isinstance(
                observation,
                dict,
            ):
                continue

            system, code, display = (
                _extract_code(
                    observation
                )
            )

            if not system or code is None:
                continue

            candidates.append(
                {
                    **observation,

                    "patient_id":
                        resource.get(
                            "patient_id",
                            observation.get(
                                "patient_id"
                            ),
                        ),

                    "encounter_id":
                        resource.get(
                            "encounter_id",
                            observation.get(
                                "encounter_id"
                            ),
                        ),

                    "resource_type":
                        "Observation",

                    "code": {
                        "system": system,
                        "code": code,
                        "display": display,
                    },

                    "parent_lab_result_id":
                        resource.get(
                            "lab_result_id"
                        )
                        or resource.get(
                            "diagnostic_report_id"
                        )
                        or resource.get("id"),
                }
            )

    return candidates


def _create_lab_signal(
    resource: Dict[str, Any],
    coded_resource: Dict[str, Any],
    match: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Create laboratory evidence.

    Result interpretation is preserved as evidence.
    No result value is hardcoded as a detection rule.
    """

    system, code, display = (
        _extract_code(
            coded_resource
        )
    )

    trigger_key = _build_trigger_key(
        system,
        str(code) if code is not None else None,
    )

    raw_values = [resource.get("conclusion"), resource.get("value")]
    observation_values = []
    observation_statuses = []
    for observation in resource.get("observations", []) if isinstance(resource.get("observations"), list) else []:
        if not isinstance(observation, dict):
            continue
        value = observation.get("value")
        if isinstance(value, dict):
            value = value.get("text") or value.get("code") or value.get("numeric")
        if value is not None:
            observation_values.append(value)
        if observation.get("status"):
            raw_values.append(observation.get("status"))
            observation_statuses.append(str(observation["status"]).strip().casefold())
    raw_values.extend(observation_values)
    raw_result = " | ".join(str(value) for value in raw_values if value is not None)
    status = str(resource.get("report_status") or resource.get("status") or "").strip().casefold()
    normalized_values = [str(value).strip().casefold() for value in raw_values if value is not None]
    text = " | ".join(normalized_values)
    if status in {"cancelled", "entered-in-error", "unknown"} or any(
        item in {"cancelled", "entered-in-error", "unknown"} for item in observation_statuses
    ):
        result_classification = "UNKNOWN"
        classification_reason = "The laboratory report status is cancelled, unknown, or entered in error."
    elif status == "preliminary" or "preliminary" in observation_statuses:
        result_classification = "PRELIMINARY"
        classification_reason = "The laboratory report is preliminary and requires final interpretation."
    elif status in {"registered", "partial", "in-progress", "in progress", "pending"} or any(
        item in {"registered", "partial", "in-progress", "in progress", "pending"}
        for item in observation_statuses
    ):
        result_classification = "PENDING"
        classification_reason = "The laboratory report is not final."
    elif any(term in text for term in ("equivocal", "borderline")):
        result_classification = "EQUIVOCAL"
        classification_reason = "The recorded result is equivocal or borderline."
    elif any(term in text for term in ("indeterminate", "inconclusive")):
        result_classification = "INDETERMINATE"
        classification_reason = "The recorded result is indeterminate or inconclusive."
    elif any(term in text for term in ("not detected", "not positive", "non-positive", "negative", "non-reactive", "nonreactive", "absent")):
        result_classification = "NEGATIVE"
        classification_reason = "The recorded result is negative."
    elif any(term in text for term in ("positive", "detected", "reactive", "present")):
        result_classification = "POSITIVE"
        classification_reason = "The recorded result contains a positive interpretation."
    else:
        result_classification = "UNKNOWN"
        classification_reason = "No recognized result interpretation is present."

    concept_key = _resolve_trigger_concept_key(match)
    disease_id = canonical_disease_id(concept_key or match.get("disease_id"))
    mapped_value_set_urls = set(match.get("value_set_urls") or [])
    if not mapped_value_set_urls:
        mapped_value_set_urls = {
            str(value_set.get("url"))
            for value_set in match.get("value_sets", [])
            if isinstance(value_set, dict) and value_set.get("url")
        }
    disease_specific_test_mapping = bool(disease_id) and (
        match.get("configured_trigger") is True
        or (
            disease_id == canonical_disease_id("measles")
            and _MEASLES_LAB_TEST_VALUE_SET_URL in mapped_value_set_urls
        )
    )
    qualifying_positive = (
        match.get("group") == "LAB_RESULT"
        and disease_specific_test_mapping
        and result_classification == "POSITIVE"
    )
    return {
        "patient_id": resource.get(
            "patient_id"
        ),

        "encounter_id": resource.get(
            "encounter_id"
        ),

        "trigger_key": trigger_key,

        "trigger_id": match.get(
            "group_id"
        ),

        "trigger_type": match.get(
            "group"
        ),

        "trigger_concept_key": concept_key,
        "disease_id": disease_id,
        "detection_priority": "HIGHEST" if qualifying_positive else "REVIEW_ONLY",

        "evidence": {
            "source_type": coded_resource.get(
                "resource_type",
                "DiagnosticReport",
            ),

            "source_id": (
                resource.get(
                    "lab_result_id"
                )
                or resource.get(
                    "diagnostic_report_id"
                )
                or resource.get("id")
            ),

            "code_system": system,

            "code": (
                str(code)
                if code is not None
                else None
            ),

            "display": display,

            "rctc_group_id": match.get(
                "group_id"
            ),

            "rctc_group": match.get(
                "group"
            ),

            "value_sets": match.get(
                "value_sets",
                [],
            ),

            "value_set_ids": match.get(
                "value_set_ids",
                [],
            ),

            "value_set_urls": match.get(
                "value_set_urls",
                [],
            ),

            "result": resource.get(
                "conclusion"
            ),

            "report_status": resource.get("report_status") or resource.get("status"),

            "observation_id":
                coded_resource.get(
                    "observation_id"
                ),

            "observation_value":
                coded_resource.get(
                    "value"
                ),
            "result_classification": result_classification,
            "classification_reason": classification_reason,
            "normalized_result": result_classification,
            "interpretation": classification_reason,
            "positive_detection_eligible": qualifying_positive,
            "disease_specific_test_mapping": disease_specific_test_mapping,
            "configured_trigger": match.get("configured_trigger") is True,
            "raw_result": raw_result,
            "specimen": resource.get("specimen"),
            "effective_time": resource.get("effective_time"),
            "collection_time": resource.get("effective_time"),
            "issued_time": resource.get("issued_time"),
            "result_time": resource.get("issued_time"),
            "source_reference": resource.get("source_lab_result_id") or resource.get("id"),
            "source_system": resource.get("source_system") or (
                resource.get("provenance", {}).get("source")
                if isinstance(resource.get("provenance"), dict)
                else None
            ),
            "provenance": resource.get("provenance"),
        },

        "confidence": 1.0,

        "detected_at": _utc_now(),
    }


# =========================================================
# Clinical Document Evidence
# =========================================================


def _extract_document_text(
    document: Dict[str, Any],
) -> Optional[str]:
    """
    Extract available clinical document text.

    This function does not diagnose the patient.

    It only exposes document content so the document
    intelligence layer can generate supporting evidence.
    """

    text = (
        document.get("extracted_text")
        or document.get("text")
        or document.get("content")
    )

    if isinstance(text, str):
        return text.strip() or None

    return None


def _create_document_signal(
    document: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    Create a document evidence signal when clinical
    document text is available.

    Document intelligence is deliberately represented as
    supporting evidence rather than a confirmed diagnosis.

    The current implementation does NOT invent an RCTC
    code from free text.
    """

    text = _extract_document_text(
        document
    )

    if not text:
        return None

    return {
        "patient_id": document.get(
            "patient_id"
        ),

        "encounter_id": document.get(
            "encounter_id"
        ),

        "trigger_key": None,

        "trigger_id": None,

        "trigger_type":
            "DOCUMENT_EVIDENCE",

        "disease_id": None,

        "evidence": {
            "source_type": "document",

            "source_id": _resource_id(
                document
            ),

            "document_type":
                document.get(
                    "document_type"
                ),

            "document_status":
                document.get(
                    "document_status"
                ),

            "title":
                document.get(
                    "title"
                ),

            "document_date":
                document.get(
                    "document_date"
                ),

            "text": text,

            "evidence_role":
                "supporting_clinical_evidence",
        },

        "confidence": 0.5,

        "detected_at": _utc_now(),
    }


# =========================================================
# Resource Detection
# =========================================================


def _detect_resource(
    resource: Dict[str, Any],
    resource_type: str,
    triggers: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """
    Detect RCTC matches for one resource.
    """

    if not isinstance(
        resource,
        dict,
    ):
        return []

    # Explicit application rules are supported alongside eRSD mappings. They
    # require an exact coding-system/code match and therefore cannot turn an
    # unmapped display name into a trigger.
    if triggers:
        candidates = (
            _get_lab_code_candidates(resource)
            if resource_type == "DiagnosticReport"
            else [resource]
        )
        configured_signals = []
        for candidate in candidates:
            system, code, _ = _extract_code(candidate)
            for trigger in triggers:
                if not isinstance(trigger, dict) or trigger.get("resource_type") != resource_type:
                    continue
                expected_system = trigger.get("code_system")
                expected_codes = {str(value) for value in trigger.get("codes", [])}
                if system != expected_system or str(code) not in expected_codes:
                    continue
                match = {
                    "group_id": trigger.get("trigger_id"),
                    "group": trigger.get("trigger_type"),
                    "disease_id": trigger.get("disease_id"),
                    "code_system": system,
                    "code": str(code),
                    "display": _extract_code(candidate)[2],
                    "value_sets": [],
                    "value_set_ids": [],
                    "value_set_urls": [],
                    "configured_trigger": True,
                }
                if trigger.get("trigger_type") == "LAB_RESULT":
                    configured_signals.append(_create_lab_signal(resource, candidate, match))
                else:
                    configured_signals.append(_create_structured_signal(candidate, match))
        if configured_signals:
            return configured_signals

    # -----------------------------------------------------
    # Laboratory resources
    # -----------------------------------------------------

    if resource_type == "DiagnosticReport":

        signals: List[Dict[str, Any]] = []

        for coded_resource in _get_lab_code_candidates(
            resource
        ):
            matches = _match_resource_against_rctc(
                coded_resource
            )

            # A single laboratory result may appear in multiple
            # eRSD/RCTC groups. For candidate detection, emit
            # one primary signal for the actual lab result.
            #
            # Priority:
            #   LAB_RESULT
            #   LAB_ORDER
            #   ALL_RESULTS
            #   EXTENDED_TIMING
            #
            # This preserves the authoritative eRSD match while
            # preventing duplicate evidence for the same resource.

            priority = {
                "LAB_RESULT": 0,
                "LAB_ORDER": 1,
                "ALL_RESULTS": 2,
                "EXTENDED_TIMING": 3,
            }

            if matches:
                primary_match = min(
                    matches,
                    key=lambda match: priority.get(
                        match.get("group"),
                        99,
                    ),
                )

                signals.append(
                    _create_lab_signal(
                        resource,
                        coded_resource,
                        primary_match,
                    )
                )

        return signals

    # -----------------------------------------------------
    # Clinical documents
    # -----------------------------------------------------

    if resource_type == "ClinicalDocument":

        signal = _create_document_signal(
            resource
        )

        return (
            [signal]
            if signal is not None
            else []
        )

    # -----------------------------------------------------
    # Other structured resources
    # -----------------------------------------------------

    matches = (
        _match_resource_against_rctc(
            resource
        )
    )

    return [
        _create_structured_signal(
            resource,
            match,
        )
        for match in matches
    ]


# =========================================================
# Main Entry Point
# =========================================================


def _detect_custom_triggers(
    resource: Dict[str, Any],
    resource_type: str,
    triggers: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Match a resource against explicitly supplied trigger definitions."""

    if not isinstance(resource, dict):
        return []

    system, code, display = _extract_code(resource)
    if not system or code is None:
        return []

    matches: List[Dict[str, Any]] = []
    for trigger in triggers:
        if not isinstance(trigger, dict):
            continue

        if trigger.get("resource_type") != resource_type:
            continue

        configured_system = _normalize_code_system(trigger.get("code_system"))
        if configured_system and configured_system != system:
            continue

        configured_codes = trigger.get("codes") or []
        if isinstance(configured_codes, list):
            code_values = {str(item) for item in configured_codes}
            if str(code) not in code_values:
                continue
        elif configured_codes is not None and str(code) != str(configured_codes):
            continue

        matches.append({
            "trigger": trigger,
            "trigger_key": _build_trigger_key(system, str(code)),
            "trigger_id": trigger.get("trigger_id"),
            "trigger_type": trigger.get("trigger_type"),
            "disease_id": trigger.get("disease_id"),
            "value_sets": [],
            "value_set_ids": [],
            "value_set_urls": [],
        })

    return [
        {
            "patient_id": resource.get("patient_id"),
            "encounter_id": resource.get("encounter_id"),
            "trigger_key": match["trigger_key"],
            "trigger_id": match["trigger_id"],
            "trigger_type": match["trigger_type"],
            "trigger_concept_key": match["trigger_id"],
            "disease_id": match["disease_id"],
            "evidence": {
                "source_type": resource.get("resource_type", resource.get("resourceType", "structured")),
                "source_id": _resource_id(resource),
                "code_system": system,
                "code": str(code),
                "display": display,
                "value_sets": match["value_sets"],
                "value_set_ids": match["value_set_ids"],
                "value_set_urls": match["value_set_urls"],
            },
            "confidence": 1.0,
            "detected_at": _utc_now(),
        }
        for match in matches
    ]


def detect_structured_triggers(
    normalized_patient: Dict[str, Any],
    triggers: Optional[
        List[Dict[str, Any]]
    ] = None,
) -> List[Dict[str, Any]]:
    """
    Generic structured candidate detection.

    Source of truth:

        eRSD v3.2.0 / RCTC

    Supported inputs:

        - Condition
        - Observation
        - Lab Result / DiagnosticReport
        - MedicationRequest
        - Procedure
        - Encounter
        - Clinical Document

    This layer does NOT determine:

        - diagnosis
        - legal reportability
        - jurisdiction
        - reporting deadline
        - case creation
        - submission
    """

    if not isinstance(
        normalized_patient,
        dict,
    ):
        raise ValueError(
            "normalized_patient must be a dictionary."
        )

    if triggers is not None:
        if not isinstance(triggers, list):
            raise ValueError("triggers must be a list when provided.")

        signals: List[Dict[str, Any]] = []
        resource_types = (
            "Condition",
            "Observation",
            "DiagnosticReport",
            "MedicationRequest",
            "Procedure",
            "Encounter",
            "ClinicalDocument",
        )
        for resource_type in resource_types:
            resources = _get_resource_list(normalized_patient, resource_type)
            for resource in resources:
                signals.extend(_detect_custom_triggers(resource, resource_type, triggers))
        return signals

    signals: List[
        Dict[str, Any]
    ] = []

    resource_types = (
        "Condition",
        "Observation",
        "DiagnosticReport",
        "MedicationRequest",
        "Procedure",
        "Encounter",
        "ClinicalDocument",
    )

    for resource_type in resource_types:

        resources = _get_resource_list(
            normalized_patient,
            resource_type,
        )

        for resource in resources:
            signals.extend(
                _detect_resource(
                    resource,
                    resource_type,
                    triggers=triggers,
                )
            )

    return signals


# =========================================================
# Explainability
# =========================================================


def explain_trigger_match(
    system: str,
    code: str,
) -> Dict[str, Any]:
    """
    Return complete eRSD/RCTC provenance for a code.
    """

    matches = match_trigger_code(
        system=system,
        code=code,
    )

    value_sets = (
        find_value_sets_containing_code(
            system=system,
            code=code,
        )
    )

    return {
        "matched": bool(matches),

        "trigger_key": _build_trigger_key(
            system,
            code,
        ),

        "code_system": system,

        "code": code,

        "rctc_matches": matches,

        "source_value_sets": value_sets,
    }


def get_trigger_index_size() -> int:
    """
    Return the number of indexed clinical
    system|code combinations.
    """

    return len(
        build_trigger_code_index()
    )
