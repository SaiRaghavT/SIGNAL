from __future__ import annotations

from typing import Any, Dict, List, Tuple

from backend.app.config.settings import settings
from backend.app.detection.disease_concepts import canonical_disease_id

_WEIGHTS = {
    "structured": settings.evidence_strength_structured_base,
    "document": settings.evidence_strength_document_base,
    "multiple_symptoms": settings.evidence_strength_multiple_symptoms_base,
    "exposure": settings.evidence_strength_exposure_base,
    "single_symptom": settings.evidence_strength_single_symptom_base,
    "quote": settings.evidence_strength_quote_bonus,
    "additional_source": settings.evidence_strength_additional_source_bonus,
    "max_source_bonus": settings.evidence_strength_max_source_bonus,
    "cross_source": settings.evidence_strength_cross_source_bonus,
}
_MAX_EVIDENCE_STRENGTH = 100.0


def _trigger_identity(
    signal: Dict[str, Any],
) -> Tuple[Any, Any]:
    """
    Return the canonical clinical concept identity used to group
    a patient's supporting signals into one condition candidate.

    Preferred identity:

        trigger_concept_key

    This can represent the shared clinical concept behind
    multiple RCTC codes.

    Fallbacks are retained for compatibility with older
    signals.
    """

    trigger_concept_key = signal.get(
        "trigger_concept_key"
    )

    if trigger_concept_key is not None:
        return (
            "concept",
            canonical_disease_id(trigger_concept_key),
        )

    disease_id = signal.get("disease_id")

    if disease_id is not None:
        return ("disease", canonical_disease_id(disease_id))

    trigger_key = signal.get(
        "trigger_key"
    )

    if trigger_key is not None:
        return (
            "trigger",
            trigger_key,
        )

    trigger_type = signal.get(
        "trigger_type"
    )

    return (
        "trigger_type",
        trigger_type,
    )


def calculate_evidence_strength(
    signals: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Return the authoritative 0-100 evidence-strength score and breakdown.

    This heuristic is not a calibrated disease probability. AI confidence is
    deliberately not read or used here.
    """
    usable: list[tuple[Dict[str, Any], Dict[str, Any], str, str]] = []
    for signal in signals:
        if not isinstance(signal, dict):
            continue
        evidence = signal.get("evidence") or {}
        if not isinstance(evidence, dict) or evidence.get("evidence_role") == "supporting_clinical_evidence":
            continue
        trigger_type = str(signal.get("trigger_type") or "").casefold()
        if evidence.get("positive_detection_eligible") is False or (
            trigger_type == "lab_result" and evidence.get("positive_detection_eligible") is not True
        ):
            continue
        usable.append((signal, evidence, trigger_type, str(evidence.get("evidence_type") or "").casefold()))

    # `positive_detection_eligible` is set upstream only after the exact
    # disease-specific code mapping and final-positive result checks pass.
    # Honor that authoritative flag across legacy lab trigger aliases.
    qualifying_lab = next((
        (signal, evidence) for signal, evidence, trigger_type, _ in usable
        if evidence.get("positive_detection_eligible") is True
        and signal.get("disease_id")
        and (
            trigger_type in {"lab_result", "laboratory", "laboratory_signal"}
            or signal.get("detection_priority") == "HIGHEST"
        )
    ), None)
    if qualifying_lab:
        _, lab_evidence = qualifying_lab
        return {
            "score": 100.0,
            "method": "weighted_rule_based_v2",
            "components": [
                {"factor": "primary_qualifying_laboratory", "points": 100.0,
                 "detail": "Configured, disease-specific positive laboratory result qualifies as the primary trigger."},
                {"factor": "evidence_strength_score", "points": 100.0,
                 "detail": "Qualifying positive laboratory evidence sets evidence strength to 100/100; supporting evidence does not stack."},
            ],
            "primary_trigger": {
                "type": "laboratory", "label": "Qualifying positive laboratory result",
                "source_id": lab_evidence.get("source_id"),
                "test_name": lab_evidence.get("display"),
                "result": lab_evidence.get("raw_result") or lab_evidence.get("result"),
            "collection_date": lab_evidence.get("effective_time"),
            "source_reference": lab_evidence.get("source_reference") or lab_evidence.get("source_id"),
                "reason": lab_evidence.get("classification_reason"),
            },
        }

    source_ids: set[str] = set()
    source_kinds: set[str] = set()
    symptom_concepts: set[str] = set()
    candidate_bases: list[tuple[float, str, str, Dict[str, Any]]] = []
    has_quoted_document_evidence = False

    for signal, evidence, trigger_type, evidence_type in usable:
        assertion = str(evidence.get("assertion") or "present").casefold()
        temporality = str(evidence.get("temporality") or "unknown").casefold()
        source_type = str(evidence.get("source_type") or "").casefold()
        is_document = (
            trigger_type.startswith("document_")
            or trigger_type == "document_evidence"
            or source_type in {"document", "clinicaldocument"}
        )
        if is_document and (assertion != "present" or temporality == "historical"):
            continue
        source_kinds.add("document" if is_document else "structured")

        source_id = evidence.get("source_id") or evidence.get("observation_id")
        if source_id is not None and str(source_id).strip():
            source_ids.add(str(source_id).strip())
        if is_document and source_id and isinstance(evidence.get("evidence_text"), str) and evidence["evidence_text"].strip():
            has_quoted_document_evidence = True

        # Only present, non-historical extracted findings qualify for symptom
        # or exposure categories. Unknown and absent assertions remain visible
        # in evidence but do not increase positive strength.
        if is_document and assertion == "present" and temporality != "historical":
            if trigger_type in {"document_diagnosis", "document_laboratory"}:
                candidate_bases.append((
                    _WEIGHTS["document"], "document_trigger",
                    "A disease-linked clinical-document trigger supports this candidate.", signal,
                ))
            elif evidence_type in {"diagnosis"}:
                candidate_bases.append((
                    _WEIGHTS["document"], "document_trigger",
                    "A present diagnosis was extracted from a linked clinical document.", signal,
                ))
            elif evidence_type in {"exposure", "epidemiology"}:
                candidate_bases.append((
                    _WEIGHTS["exposure"], "exposure_trigger",
                    "A present exposure or epidemiological link was extracted from a clinical document.", signal,
                ))
            elif evidence_type == "symptom":
                concept = " ".join(str(evidence.get("concept") or "").casefold().split())
                if concept:
                    symptom_concepts.add(concept)

        # A structured score requires an actual configured trigger identity;
        # arbitrary observations and unmapped records are not assigned 60.
        if not is_document and signal.get("trigger_id") and trigger_type != "lab_result":
            candidate_bases.append((
                _WEIGHTS["structured"], "structured_trigger",
                "A configured structured clinical trigger matched this record.", signal,
            ))

    if symptom_concepts:
        symptom_weight = _WEIGHTS["multiple_symptoms"] if len(symptom_concepts) >= 2 else _WEIGHTS["single_symptom"]
        symptom_detail = (
            f"{len(symptom_concepts)} distinct present symptoms were extracted from linked clinical notes."
            if len(symptom_concepts) >= 2 else "One present symptom was extracted from a linked clinical note."
        )
        candidate_bases.append((symptom_weight, "symptom_trigger", symptom_detail, {}))

    if not candidate_bases:
        return {"score": 0.0, "method": "weighted_rule_based_v2", "components": [], "primary_trigger": None}

    base_score, base_factor, base_detail, primary_signal = max(candidate_bases, key=lambda item: item[0])
    primary_evidence = primary_signal.get("evidence") or {}
    primary_source_id = primary_evidence.get("source_id") or primary_evidence.get("observation_id")
    # IDs are globally deduplicated, independent of signal count or modality.
    additional_record_count = max(0, len(source_ids) - 1)
    source_bonus = min(_WEIGHTS["max_source_bonus"], additional_record_count * _WEIGHTS["additional_source"])
    modality_bonus = _WEIGHTS["cross_source"] if len(source_kinds) > 1 else 0.0
    quote_bonus = _WEIGHTS["quote"] if has_quoted_document_evidence else 0.0
    score = min(_MAX_EVIDENCE_STRENGTH, base_score + source_bonus + modality_bonus + quote_bonus)

    components = [{"factor": base_factor, "points": round(base_score, 2), "detail": base_detail}]
    if source_bonus:
        components.append({
            "factor": "distinct_source_record_support", "points": round(source_bonus, 2),
            "detail": f"{additional_record_count} additional distinct source record(s); repeated IDs count once.",
        })
    if modality_bonus:
        components.append({"factor": "cross_source_type_support", "points": round(modality_bonus, 2),
                           "detail": "Both structured records and clinical documents support the candidate."})
    if quote_bonus:
        components.append({"factor": "quoted_document_evidence", "points": round(quote_bonus, 2),
                           "detail": "A source-linked clinical-document quote supports the candidate."})
    components.append({"factor": "evidence_strength_score", "points": round(score, 2),
                       "detail": "Weighted heuristic score; not a calibrated probability."})
    primary_type = {
        "structured_trigger": "structured", "document_trigger": "document",
        "symptom_trigger": "symptom", "exposure_trigger": "exposure",
    }.get(base_factor, "evidence")
    return {
        "score": round(score, 2),
        "method": "weighted_rule_based_v2",
        "components": components,
        "primary_trigger": {
            "type": primary_type,
            "label": base_detail,
            "source_id": primary_source_id,
        },
    }


def _create_candidate(
    signals: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Create a POTENTIAL candidate from fused evidence.

    Candidate Fusion does not determine:

        - diagnosis
        - reportability
        - jurisdiction
        - deadline
        - case creation
        - submission
    """

    if not signals:
        raise ValueError(
            "Cannot create a candidate from empty signals."
        )

    first_signal = signals[0]

    evidence = [
        signal.get(
            "evidence",
            {},
        )
        for signal in signals
    ]

    evidence_source_types = list(
        dict.fromkeys(
            item.get("source_type")
            for item in evidence
            if (
                isinstance(item, dict)
                and item.get(
                    "source_type"
                ) is not None
            )
        )
    )

    strength = calculate_evidence_strength(signals)
    detection_priority = (
        "HIGHEST"
        if any(
            signal.get("detection_priority") == "HIGHEST"
            and (signal.get("evidence") or {}).get("positive_detection_eligible") is True
            for signal in signals
        )
        else "STANDARD"
    )

    encounter_ids = list(
        dict.fromkeys(
            signal.get(
                "encounter_id"
            )
            for signal in signals
            if signal.get(
                "encounter_id"
            ) is not None
        )
    )

    encounter_id = (
        encounter_ids[0]
        if len(encounter_ids) == 1
        else None
    )

    trigger_types = list(
        dict.fromkeys(
            signal.get(
                "trigger_type"
            )
            for signal in signals
            if signal.get(
                "trigger_type"
            ) is not None
        )
    )

    trigger_keys = list(
        dict.fromkeys(
            signal.get(
                "trigger_key"
            )
            for signal in signals
            if signal.get(
                "trigger_key"
            ) is not None
        )
    )

    trigger_concept_keys = list(
        dict.fromkeys(
            signal.get(
                "trigger_concept_key"
            )
            for signal in signals
            if signal.get(
                "trigger_concept_key"
            ) is not None
        )
    )

    return {
        "patient_id": first_signal.get(
            "patient_id"
        ),

        "encounter_id": encounter_id,

        # Retained for compatibility.
        "disease_id": canonical_disease_id(
            first_signal.get("trigger_concept_key") or first_signal.get("disease_id")
        ),

        # Shared clinical concept.
        "trigger_concept_key": (
            trigger_concept_keys[0]
            if len(trigger_concept_keys) == 1
            else None
        ),

        "trigger_concept_keys": (
            trigger_concept_keys
        ),

        # Exact coded trigger identities.
        "trigger_key": (
            trigger_keys[0]
            if len(trigger_keys) == 1
            else None
        ),

        "trigger_keys": trigger_keys,

        "status": "POTENTIAL",

        "trigger_type": (
            trigger_types[0]
            if trigger_types
            else None
        ),

        "trigger_types": trigger_types,

        "evidence": evidence,

        "evidence_source_types": (
            evidence_source_types
        ),

        "supporting_signal_count": len(
            signals
        ),

        # Explicit API fields distinguish this heuristic from model confidence.
        "evidence_strength": strength["score"],

        "evidence_strength_method": strength["method"],

        "evidence_strength_components": strength["components"],

        "primary_trigger": strength.get("primary_trigger"),

        # Evidence ordering is independent of the heuristic strength score.
        "detection_priority": detection_priority,

        "detected_at": first_signal.get(
            "detected_at"
        ),

        # Preserve raw signals for explainability.
        "signals": signals,
    }


def fuse_candidate_signals(
    signals: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Fuse structured and document signals into one explainable
    POTENTIAL candidate per patient and canonical clinical concept.

    Fusion is intentionally independent of:

        - Texas
        - jurisdiction
        - state rules
        - reporting deadlines
        - legal reportability
        - case creation
        - submission
    """

    if not isinstance(
        signals,
        list,
    ):
        raise ValueError(
            "signals must be a list."
        )

    # The canonical adapter can expose one lab observation both directly
    # and nested under its DiagnosticReport. Drop only duplicate references
    # to the same coded source; distinct tests remain separate evidence.
    unique_signals: List[Dict[str, Any]] = []
    source_refs: Dict[Tuple[Any, Any, Any], set[str]] = {}
    for signal in signals:
        if not isinstance(signal, dict):
            continue
        evidence = signal.get("evidence") or {}
        if not isinstance(evidence, dict):
            evidence = {}
        signal_type = str(signal.get("trigger_type") or "").casefold()
        source_type = str(evidence.get("source_type") or "").casefold()
        has_disease_identity = any(
            signal.get(key)
            for key in ("disease_id", "trigger_concept_key", "trigger_key")
        )
        # A source-note record is useful for traceability, but it has no
        # disease identity and must never become a standalone candidate.
        if (
            evidence.get("evidence_role") == "supporting_clinical_evidence"
            or (
                not has_disease_identity
                and (
                    source_type in {"document", "clinicaldocument"}
                    or signal_type in {"document_evidence", "document_diagnosis"}
                )
            )
        ):
            continue
        refs = {
            str(value)
            for value in (evidence.get("source_id"), evidence.get("observation_id"))
            if value is not None
        }
        code_identity = evidence.get("trigger_key") or signal.get("trigger_key")
        dedupe_key = (signal.get("patient_id"), signal.get("encounter_id"), code_identity)
        known_refs = source_refs.setdefault(dedupe_key, set())
        if refs and known_refs.intersection(refs):
            continue
        known_refs.update(refs)
        unique_signals.append(signal)

    candidate_groups: Dict[
        Tuple[Any, Any],
        List[Dict[str, Any]],
    ] = {}

    # Group by patient and canonical clinical concept across encounters.
    # Encounter IDs stay on each signal and are retained in the evidence.

    for signal in unique_signals:

        if not isinstance(
            signal,
            dict,
        ):
            continue

        patient_id = signal.get(
            "patient_id"
        )

        trigger_identity = (
            _trigger_identity(
                signal
            )
        )

        key = (patient_id, trigger_identity)
        candidate_groups.setdefault(key, []).append(signal)

    return [
        _create_candidate(
            group
        )
        for group in candidate_groups.values()
        if group
    ]
