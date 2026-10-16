from __future__ import annotations

import re
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

from backend.app.detection.disease_concepts import canonical_disease_id
from backend.app.detection.trigger_loader import build_trigger_code_index, get_value_sets


# These are the official eRSD RCTC groups whose disease-focused value sets can
# identify a diagnosis or laboratory concept in extracted document evidence.
_DOCUMENT_TRIGGER_GROUP_TYPES = {
    "dxtc-3.2.0": "diagnosis",
    "sdtc-3.2.0": "diagnosis",
    "lrtc-3.2.0": "laboratory",
    "lotc-3.2.0": "laboratory",
    "ostc-3.2.0": "laboratory",
}

# Keep the original measles aliases as a compatibility fallback for terminology
# releases whose display strings differ from the extracted concept text.
_LEGACY_DOCUMENT_TRIGGERS = (
    {
        "trigger_id": "measles-document-diagnosis",
        "disease_id": "measles",
        "evidence_type": "diagnosis",
        "trigger_type": "DOCUMENT_DIAGNOSIS",
        "terms": ("measles", "rubeola"),
    },
    {
        "trigger_id": "measles-positive-document-lab",
        "disease_id": "measles",
        "evidence_type": "laboratory",
        "trigger_type": "DOCUMENT_LABORATORY",
        "terms": ("measles", "rubeola"),
    },
)

_NEGATION_BEFORE = re.compile(
    r"\b(?:no|not|deny|denies|denied|negative for|rule[sd]? out|without|"
    r"absence of|no evidence of)\b[^.!?]{0,100}$",
    re.IGNORECASE,
)
_NEGATION_AFTER = re.compile(
    r"^[^.!?]{0,100}\b(?:ruled out|not detected|negative|absent|unlikely|"
    r"not present)\b",
    re.IGNORECASE,
)
_DISEASE_LABEL_STOP_WORDS = {
    "acute", "chronic", "confirmed", "disease", "disorder", "infection",
    "possible", "suspected", "situation", "unspecified",
}


def _normalized_term(value: Any) -> str:
    text = str(value or "").casefold().strip()
    text = re.sub(r"\s+\((?:disorder|finding|situation|organism|event)\)$", "", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def _value_set_focuses(value_set: dict[str, Any]) -> list[tuple[str, str, str]]:
    focuses: list[tuple[str, str, str]] = []
    use_contexts = value_set.get("useContext") or value_set.get("use_context") or []
    if isinstance(use_contexts, dict):
        use_contexts = [use_contexts]
    for context in use_contexts:
        if not isinstance(context, dict):
            continue
        if (context.get("code") or {}).get("code") != "focus":
            continue
        concept = context.get("valueCodeableConcept") or context.get("value_codeable_concept") or {}
        for coding in concept.get("coding") or []:
            if isinstance(coding, dict) and coding.get("system") and coding.get("code"):
                focuses.append((str(coding["system"]), str(coding["code"]), str(concept.get("text") or "")))
    return focuses


def _has_reporting_trigger_context(value_set: dict[str, Any]) -> bool:
    use_contexts = value_set.get("useContext") or value_set.get("use_context") or []
    if isinstance(use_contexts, dict):
        use_contexts = [use_contexts]
    for context in use_contexts:
        if not isinstance(context, dict) or (context.get("code") or {}).get("code") != "reporting":
            continue
        concept = context.get("valueCodeableConcept") or context.get("value_codeable_concept") or {}
        if any(
            isinstance(coding, dict) and str(coding.get("code", "")).casefold() == "triggering"
            for coding in concept.get("coding") or []
        ):
            return True
    return False


def _walk_expansion(contains: Any):
    for item in contains if isinstance(contains, list) else []:
        if not isinstance(item, dict):
            continue
        yield item
        yield from _walk_expansion(item.get("contains"))


@lru_cache(maxsize=1)
def _document_trigger_catalog() -> tuple[dict[str, Any], ...]:
    """Build disease aliases from reporting-focused eRSD value sets."""
    code_index = build_trigger_code_index()
    seen_value_sets: set[tuple[str, str, str]] = set()
    catalog: dict[tuple[str, str, str, str], dict[str, Any]] = {}

    for value_set in get_value_sets().values():
        if not isinstance(value_set, dict):
            continue
        identity = (
            str(value_set.get("id") or ""),
            str(value_set.get("url") or ""),
            str(value_set.get("version") or ""),
        )
        if identity in seen_value_sets:
            continue
        seen_value_sets.add(identity)
        if not _has_reporting_trigger_context(value_set):
            continue

        for focus_system, focus_code, focus_text in _value_set_focuses(value_set):
            disease_id = canonical_disease_id(f"{focus_system}|{focus_code}")
            for item in _walk_expansion((value_set.get("expansion") or {}).get("contains")):
                if item.get("inactive") is True or not item.get("display"):
                    continue
                item_key = f"{item.get('system')}|{item.get('code')}"
                group_ids = {
                    match.get("group_id")
                    for match in code_index.get(item_key, [])
                }
                for group_id, evidence_type in _DOCUMENT_TRIGGER_GROUP_TYPES.items():
                    if group_id not in group_ids:
                        continue
                    term = _normalized_term(item["display"])
                    if len(term) < 4:
                        continue
                    key = (group_id, evidence_type, str(disease_id), term)
                    catalog[key] = {
                        "trigger_id": f"ersd-{group_id}-{focus_code}",
                        "disease_id": disease_id,
                        "evidence_type": evidence_type,
                        "trigger_type": "DOCUMENT_DIAGNOSIS" if evidence_type == "diagnosis" else "DOCUMENT_LABORATORY",
                        "terms": (term,),
                    }
                    focus_term = _normalized_term(focus_text)
                    if len(focus_term) >= 4:
                        catalog[(group_id, evidence_type, str(disease_id), focus_term)] = {
                            "trigger_id": f"ersd-{group_id}-{focus_code}",
                            "disease_id": disease_id,
                            "evidence_type": evidence_type,
                            "trigger_type": "DOCUMENT_DIAGNOSIS" if evidence_type == "diagnosis" else "DOCUMENT_LABORATORY",
                            "terms": (focus_term,),
                        }

    return tuple(catalog.values())


def _matching_document_triggers(evidence: dict[str, Any]) -> list[dict[str, Any]]:
    evidence_type = str(evidence.get("evidence_type", "")).casefold()
    concept = _normalized_term(evidence.get("concept"))
    if not concept:
        return []

    catalog = (*_document_trigger_catalog(), *_LEGACY_DOCUMENT_TRIGGERS)
    matches: list[tuple[int, dict[str, Any]]] = []
    for trigger in catalog:
        if evidence_type != trigger["evidence_type"]:
            continue
        for raw_term in trigger["terms"]:
            term = _normalized_term(raw_term)
            if term and (
                concept == term
                or (len(term) >= 5 and term in concept)
                or (len(concept) >= 12 and len(concept.split()) >= 2 and concept in term)
            ):
                matches.append((len(term), trigger))

    if not matches:
        return []
    best_length = max(length for length, _ in matches)
    best = {
        (canonical_disease_id(trigger["disease_id"]), trigger["evidence_type"]): trigger
        for length, trigger in matches
        if length == best_length
    }
    # Ambiguous term matches should not invent a disease association.
    return list(best.values()) if len(best) == 1 else []


def _is_explicitly_negated(evidence: dict[str, Any], trigger: dict[str, Any]) -> bool:
    concept = str(evidence.get("concept") or "")
    evidence_text = str(evidence.get("evidence_text") or "")
    combined = _normalized_term(f"{concept}. {evidence_text}")
    for raw_term in trigger["terms"]:
        term = _normalized_term(raw_term)
        if not term:
            continue
        term_pattern = re.escape(term).replace(r"\ ", r"\s+")
        expression = re.compile(rf"\b{term_pattern}\b", re.IGNORECASE)
        for match in expression.finditer(combined):
            before = combined[max(0, match.start() - 100):match.start()]
            after = combined[match.end():match.end() + 100]
            if _NEGATION_BEFORE.search(before) or _NEGATION_AFTER.search(after):
                return True
    return False


def _matches_document_trigger(evidence: dict[str, Any], trigger: dict[str, Any]) -> bool:
    if str(evidence.get("assertion", "uncertain")).casefold() != "present":
        return False
    if str(evidence.get("temporality", "unknown")).casefold() == "historical":
        return False
    if _is_explicitly_negated(evidence, trigger):
        return False
    if trigger["evidence_type"] == "laboratory":
        return bool(re.search(r"\b(positive|detected|reactive)\b", str(evidence.get("evidence_text") or ""), re.IGNORECASE))
    return True


def _structured_disease_terms(signal: dict[str, Any]) -> set[str]:
    """Get disease-name tokens from an already matched structured trigger."""

    evidence = signal.get("evidence") or {}
    label = str(evidence.get("display") or evidence.get("concept") or "")
    return {
        token.casefold()
        for token in re.findall(r"[A-Za-z][A-Za-z'-]{2,}", label)
        if token.casefold() not in _DISEASE_LABEL_STOP_WORDS
    }


def _evidence_matches_disease(
    item: dict[str, Any],
    disease_terms: set[str],
) -> bool:
    concept = str(item.get("concept") or "")
    concept_terms = {token.casefold() for token in re.findall(r"[A-Za-z][A-Za-z'-]{2,}", concept)}
    return bool(disease_terms & concept_terms)


def detect_document_triggers(
    evidence_items: list[dict[str, Any]],
    patient_id: str,
    structured_signals: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Convert explicit document evidence into explainable candidate signals.

    Document diagnosis and positive laboratory evidence can match disease-focused
    eRSD RCTC value sets. Other document evidence can support a disease already
    matched by structured data, without treating symptoms alone as diagnoses.
    """

    if not isinstance(evidence_items, list):
        raise ValueError("evidence_items must be a list.")

    signals: list[dict[str, Any]] = []
    emitted: set[tuple[str, str, str, str]] = set()
    for item in evidence_items:
        if not isinstance(item, dict):
            continue

        for trigger in _matching_document_triggers(item):
            if not _matches_document_trigger(item, trigger):
                continue

            confidence = item.get("confidence")
            if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
                confidence = 0.75

            signal = {
                    "patient_id": patient_id,
                    "encounter_id": item.get("encounter_id"),
                    "trigger_id": trigger["trigger_id"],
                    "trigger_type": trigger["trigger_type"],
                    "disease_id": canonical_disease_id(trigger["disease_id"]),
                    "trigger_concept_key": canonical_disease_id(trigger["disease_id"]),
                    "evidence": {
                        "source_type": item.get("source_type") or "ClinicalDocument",
                        "source_id": item.get("document_id"),
                        "evidence_type": item.get("evidence_type"),
                        "concept": item.get("concept"),
                        "evidence_text": item.get("evidence_text"),
                        "source_title": item.get("source_title"),
                    },
                    "confidence": max(0.0, min(float(confidence), 1.0)),
                    "detected_at": datetime.now(timezone.utc).isoformat(),
                }
            signals.append(signal)
            emitted.add((
                str(signal["disease_id"]),
                str(item.get("document_id") or ""),
                str(item.get("evidence_type") or ""),
                str(item.get("concept") or ""),
            ))

    disease_groups: dict[str, tuple[dict[str, Any], set[str]]] = {}
    for signal in structured_signals or []:
        disease_id = signal.get("disease_id")
        terms = _structured_disease_terms(signal)
        if disease_id and terms:
            group = disease_groups.setdefault(str(disease_id), (signal, set()))
            group[1].update(terms)

    for disease_id, (structured_signal, disease_terms) in disease_groups.items():
        anchored_documents = {
            str(item.get("document_id"))
            for item in evidence_items
            if isinstance(item, dict)
            and item.get("document_id")
            and str(item.get("evidence_type", "")).casefold() in {"diagnosis", "laboratory"}
            and str(item.get("assertion", "uncertain")).casefold() in {"present", "uncertain"}
            and str(item.get("temporality", "unknown")).casefold() != "historical"
            and _evidence_matches_disease(item, disease_terms)
        }
        if not anchored_documents:
            continue

        for item in evidence_items:
            if not isinstance(item, dict):
                continue
            document_id = str(item.get("document_id") or "")
            if not document_id or document_id not in anchored_documents:
                continue
            evidence_type = str(item.get("evidence_type") or "").casefold()
            concept = str(item.get("concept") or "")
            dedupe_key = (disease_id, document_id, evidence_type, concept)
            if dedupe_key in emitted:
                continue

            confidence = item.get("confidence")
            if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
                confidence = 0.75
            signals.append(
                {
                    "patient_id": patient_id,
                    "encounter_id": item.get("encounter_id") or structured_signal.get("encounter_id"),
                    "trigger_id": f"document-evidence-{evidence_type or 'finding'}",
                    "trigger_type": "DOCUMENT_EVIDENCE",
                    "disease_id": disease_id,
                    "trigger_concept_key": structured_signal.get("trigger_concept_key") or disease_id,
                    "evidence": {
                        "source_type": item.get("source_type") or "ClinicalDocument",
                        "source_id": item.get("document_id"),
                        "evidence_type": item.get("evidence_type"),
                        "concept": item.get("concept"),
                        "evidence_text": item.get("evidence_text"),
                        "assertion": item.get("assertion"),
                        "temporality": item.get("temporality"),
                        "source_title": item.get("source_title"),
                    },
                    "confidence": max(0.0, min(float(confidence), 1.0)),
                    "detected_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            emitted.add(dedupe_key)

    return signals
