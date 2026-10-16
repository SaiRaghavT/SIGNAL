from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from backend.app.detection.disease_concepts import canonical_disease_id


# Document signals are intentionally conservative: an explicit diagnosis
# can create a candidate signal; symptom-only evidence cannot confirm one.
# Add disease-specific rules here as the detection scope expands.
DOCUMENT_DIAGNOSIS_TRIGGERS = [
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
]

_NEGATED_DIAGNOSIS_PATTERNS = (
    re.compile(
        r"\b(?:no|not|denies?|negative for|rule[sd]? out|without|absence of)"
        r"\b[^.!?]{0,60}\b(?:measles|rubeola)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:measles|rubeola)\b[^.!?]{0,60}"
        r"\b(?:ruled out|not detected|negative|absent|unlikely)\b",
        re.IGNORECASE,
    ),
)
_DISEASE_LABEL_STOP_WORDS = {
    "acute", "chronic", "confirmed", "disease", "disorder", "infection",
    "possible", "suspected", "situation", "unspecified",
}


def _matches_document_trigger(
    evidence: dict[str, Any],
    trigger: dict[str, Any],
) -> bool:
    if (
        str(evidence.get("evidence_type", "")).casefold()
        != trigger["evidence_type"]
    ):
        return False

    assertion = str(evidence.get("assertion", "uncertain")).casefold()
    temporality = str(evidence.get("temporality", "unknown")).casefold()
    if assertion != "present" or temporality == "historical":
        return False

    concept = str(evidence.get("concept") or "")
    evidence_text = str(evidence.get("evidence_text") or "")
    combined = f"{concept}. {evidence_text}"

    if any(pattern.search(combined) for pattern in _NEGATED_DIAGNOSIS_PATTERNS):
        return False

    has_disease_term = any(
        re.search(rf"\b{re.escape(term)}\b", concept, re.IGNORECASE)
        for term in trigger["terms"]
    )
    if not has_disease_term:
        return False

    if trigger["evidence_type"] == "laboratory":
        return assertion == "present" and bool(
            re.search(
                r"\b(positive|detected|reactive)\b",
                evidence_text,
                re.IGNORECASE,
            )
        )

    # A differential or suspected diagnosis is useful chart context, but it
    # should not create its own candidate when no diagnosis is asserted.
    return assertion == "present"


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

    Document evidence is attached to a disease only when that disease already
    matched a structured eRSD trigger, or when an existing explicit document
    trigger (currently measles) matches. This lets document findings support
    any structured disease without treating symptoms as diagnoses.
    """

    if not isinstance(evidence_items, list):
        raise ValueError("evidence_items must be a list.")

    signals: list[dict[str, Any]] = []
    emitted: set[tuple[str, str, str, str]] = set()
    for item in evidence_items:
        if not isinstance(item, dict):
            continue

        for trigger in DOCUMENT_DIAGNOSIS_TRIGGERS:
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
                        "source_type": "ClinicalDocument",
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
                        "source_type": "ClinicalDocument",
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
