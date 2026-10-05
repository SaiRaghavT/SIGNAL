from __future__ import annotations

from typing import Any, Dict, List


def extract_candidate_features(
    signals: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Convert a group of candidate signals into ML-ready features.

    These features describe the strength and diversity of the
    evidence supporting a potential candidate.
    """

    if not isinstance(signals, list):
        raise ValueError("signals must be a list.")

    valid_signals = [
        signal
        for signal in signals
        if isinstance(signal, dict)
    ]

    trigger_types = {
        signal.get("trigger_type")
        for signal in valid_signals
        if signal.get("trigger_type") is not None
    }

    evidence_source_types = set()

    for signal in valid_signals:
        evidence = signal.get("evidence")

        if isinstance(evidence, dict):
            source_type = evidence.get("source_type")

            if source_type is not None:
                evidence_source_types.add(source_type)

    confidence_values = [
        signal.get("confidence")
        for signal in valid_signals
        if isinstance(signal.get("confidence"), (int, float))
    ]

    condition_signal_present = int(
        "CONDITION_CODE" in trigger_types
    )

    lab_signal_present = int(
        "LAB_RESULT" in trigger_types
    )

    document_signal_present = int(
        any(
            trigger_type
            for trigger_type in trigger_types
            if str(trigger_type).startswith("DOCUMENT_")
        )
    )

    positive_lab_present = int(
        lab_signal_present
    )

    supporting_signal_count = len(valid_signals)

    evidence_source_count = len(evidence_source_types)

    max_signal_confidence = (
        max(confidence_values)
        if confidence_values
        else 0.0
    )

    avg_signal_confidence = (
        sum(confidence_values) / len(confidence_values)
        if confidence_values
        else 0.0
    )

    has_encounter = int(
        any(
            signal.get("encounter_id") is not None
            for signal in valid_signals
        )
    )

    multiple_signal_types = int(
        len(trigger_types) > 1
    )

    return {
        "condition_signal_present": condition_signal_present,
        "lab_signal_present": lab_signal_present,
        "document_signal_present": document_signal_present,
        "positive_lab_present": positive_lab_present,
        "supporting_signal_count": supporting_signal_count,
        "evidence_source_count": evidence_source_count,
        "max_signal_confidence": max_signal_confidence,
        "avg_signal_confidence": avg_signal_confidence,
        "has_encounter": has_encounter,
        "multiple_signal_types": multiple_signal_types,
    }