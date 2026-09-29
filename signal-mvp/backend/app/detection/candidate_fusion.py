from __future__ import annotations

from typing import Any, Dict, List


def _same_patient_and_disease(
    signal_a: Dict[str, Any],
    signal_b: Dict[str, Any],
) -> bool:
    return (
        signal_a.get("patient_id") == signal_b.get("patient_id")
        and signal_a.get("disease_id") == signal_b.get("disease_id")
    )


def _can_fuse(
    signal_a: Dict[str, Any],
    signal_b: Dict[str, Any],
) -> bool:
    """
    Determine whether two candidate signals refer to the same
    potential clinical event.

    Signals must belong to the same patient and disease.

    Encounter handling:
    - Same encounter -> fuse.
    - One encounter is missing -> allow fusion.
    - Different known encounters -> keep separate.
    """

    if not _same_patient_and_disease(signal_a, signal_b):
        return False

    encounter_a = signal_a.get("encounter_id")
    encounter_b = signal_b.get("encounter_id")

    if encounter_a is None or encounter_b is None:
        return True

    return encounter_a == encounter_b


def _create_candidate(
    signals: List[Dict[str, Any]],
) -> Dict[str, Any]:

    first_signal = signals[0]

    evidence = [
        signal.get("evidence", {})
        for signal in signals
    ]

    confidence_values = [
        signal.get("confidence")
        for signal in signals
        if isinstance(signal.get("confidence"), (int, float))
    ]

    confidence = (
        max(confidence_values)
        if confidence_values
        else None
    )

    encounter_ids = [
        signal.get("encounter_id")
        for signal in signals
        if signal.get("encounter_id") is not None
    ]

    encounter_id = (
        encounter_ids[0]
        if encounter_ids
        else None
    )

    return {
        "patient_id": first_signal.get("patient_id"),
        "encounter_id": encounter_id,
        "disease_id": first_signal.get("disease_id"),
        "status": "POTENTIAL",
        "trigger_type": first_signal.get("trigger_type"),
        "evidence": evidence,
        "confidence": confidence,
        "detected_at": first_signal.get("detected_at"),
        "signals": signals,
    }


def fuse_candidate_signals(
    signals: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:

    if not isinstance(signals, list):
        raise ValueError("signals must be a list.")

    candidates: List[List[Dict[str, Any]]] = []

    for signal in signals:

        if not isinstance(signal, dict):
            continue

        matched_group = None

        for group in candidates:
            if _can_fuse(signal, group[0]):
                matched_group = group
                break

        if matched_group is not None:
            matched_group.append(signal)
        else:
            candidates.append([signal])

    return [
        _create_candidate(group)
        for group in candidates
        if group
    ]