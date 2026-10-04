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

    Signals fuse directly only when their encounter IDs match. Patient-level
    signals without an encounter are attached after encounter groups form.
    """

    if not _same_patient_and_disease(signal_a, signal_b):
        return False

    encounter_a = signal_a.get("encounter_id")
    encounter_b = signal_b.get("encounter_id")

    return encounter_a == encounter_b


def _create_candidate(
    signals: List[Dict[str, Any]],
) -> Dict[str, Any]:

    first_signal = signals[0]

    evidence = [
        signal.get("evidence", {})
        for signal in signals
    ]
    evidence_source_types = list(
        dict.fromkeys(
            item.get("source_type")
            for item in evidence
            if isinstance(item, dict) and item.get("source_type") is not None
        )
    )

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
    trigger_types = list(
        dict.fromkeys(
            signal.get("trigger_type")
            for signal in signals
            if signal.get("trigger_type") is not None
        )
    )

    return {
        "patient_id": first_signal.get("patient_id"),
        "encounter_id": encounter_id,
        "disease_id": first_signal.get("disease_id"),
        "status": "POTENTIAL",
        "trigger_type": first_signal.get("trigger_type"),
        "trigger_types": trigger_types,
        "evidence": evidence,
        "evidence_source_types": evidence_source_types,
        "supporting_signal_count": len(signals),
        "confidence": confidence,
        "detected_at": first_signal.get("detected_at"),
        "signals": signals,
    }


def fuse_candidate_signals(
    signals: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:

    if not isinstance(signals, list):
        raise ValueError("signals must be a list.")

    encounter_groups: List[List[Dict[str, Any]]] = []
    patient_level_groups: Dict[tuple[Any, Any], List[Dict[str, Any]]] = {}

    for signal in signals:

        if not isinstance(signal, dict):
            continue

        if signal.get("encounter_id") is None:
            key = (signal.get("patient_id"), signal.get("disease_id"))
            patient_level_groups.setdefault(key, []).append(signal)
            continue

        for group in encounter_groups:
            if _can_fuse(signal, group[0]):
                group.append(signal)
                break
        else:
            encounter_groups.append([signal])

    candidates = list(encounter_groups)
    for key, group in patient_level_groups.items():
        related_groups = []
        for event_group in encounter_groups:
            event_key = (
                event_group[0].get("patient_id"),
                event_group[0].get("disease_id"),
            )
            if event_key == key:
                related_groups.append(event_group)
        if len(related_groups) == 1:
            related_groups[0].extend(group)
        else:
            # With zero or multiple matching encounters, preserve the evidence
            # as its own patient-level potential instead of assigning it to an
            # arbitrary encounter.
            candidates.append(group)

    return [
        _create_candidate(group)
        for group in candidates
        if group
    ]
