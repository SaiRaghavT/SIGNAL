from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any


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
    if assertion == "absent" or temporality == "historical":
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

    return True


def detect_document_triggers(
    evidence_items: list[dict[str, Any]],
    patient_id: str,
) -> list[dict[str, Any]]:
    """Convert explicitly extracted document diagnoses into candidate signals."""

    if not isinstance(evidence_items, list):
        raise ValueError("evidence_items must be a list.")

    signals: list[dict[str, Any]] = []
    for item in evidence_items:
        if not isinstance(item, dict):
            continue

        for trigger in DOCUMENT_DIAGNOSIS_TRIGGERS:
            if not _matches_document_trigger(item, trigger):
                continue

            confidence = item.get("confidence")
            if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
                confidence = 0.75

            signals.append(
                {
                    "patient_id": patient_id,
                    "encounter_id": item.get("encounter_id"),
                    "trigger_id": trigger["trigger_id"],
                    "trigger_type": trigger["trigger_type"],
                    "disease_id": trigger["disease_id"],
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
            )

    return signals
