from __future__ import annotations

from typing import Any, Dict, List, Tuple


def _trigger_identity(
    signal: Dict[str, Any],
) -> Tuple[Any, Any]:
    """
    Return the identity used to determine whether two signals
    belong to the same potential clinical event.

    Preferred identity:

        trigger_concept_key

    This can represent the shared clinical concept behind
    multiple RCTC codes.

    Fallbacks are retained for compatibility with older
    signals.
    """

    disease_id = signal.get("disease_id")

    if disease_id is not None:
        return ("disease", disease_id)

    trigger_concept_key = signal.get(
        "trigger_concept_key"
    )

    if trigger_concept_key is not None:
        return (
            "concept",
            trigger_concept_key,
        )

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


def _same_patient_and_trigger(
    signal_a: Dict[str, Any],
    signal_b: Dict[str, Any],
) -> bool:
    """
    Signals can only be fused when they belong to the same
    patient and represent the same clinical trigger concept.
    """

    if (
        signal_a.get("patient_id")
        != signal_b.get("patient_id")
    ):
        return False

    return (
        _trigger_identity(signal_a)
        == _trigger_identity(signal_b)
    )


def _can_fuse(
    signal_a: Dict[str, Any],
    signal_b: Dict[str, Any],
) -> bool:
    """
    Determine whether two signals refer to the same
    potential clinical event.

    Requirements:

    1. Same patient
    2. Same clinical trigger concept
    3. Same encounter when both have encounters

    Patient-level evidence without an encounter is handled
    separately after encounter groups are formed.
    """

    if not _same_patient_and_trigger(
        signal_a,
        signal_b,
    ):
        return False

    encounter_a = signal_a.get(
        "encounter_id"
    )

    encounter_b = signal_b.get(
        "encounter_id"
    )

    if (
        encounter_a is not None
        and encounter_b is not None
    ):
        return encounter_a == encounter_b

    return False


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

    confidence_values = [
        signal.get(
            "confidence"
        )
        for signal in signals
        if isinstance(
            signal.get(
                "confidence"
            ),
            (int, float),
        )
    ]

    confidence = (
        max(confidence_values)
        if confidence_values
        else None
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
        "disease_id": first_signal.get(
            "disease_id"
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

        "confidence": confidence,

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
    Fuse structured and document candidate signals into
    explainable POTENTIAL candidates.

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

    encounter_groups: List[
        List[Dict[str, Any]]
    ] = []

    patient_level_groups: Dict[
        Tuple[Any, Any],
        List[Dict[str, Any]],
    ] = {}

    # =====================================================
    # Build encounter-level groups
    # =====================================================

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

        # -------------------------------------------------
        # Patient-level evidence
        # -------------------------------------------------

        if signal.get(
            "encounter_id"
        ) is None:

            key = (
                patient_id,
                trigger_identity,
            )

            patient_level_groups.setdefault(
                key,
                [],
            ).append(
                signal
            )

            continue

        # -------------------------------------------------
        # Encounter-level evidence
        # -------------------------------------------------

        for group in encounter_groups:

            if not group:
                continue

            if _can_fuse(
                signal,
                group[0],
            ):
                group.append(
                    signal
                )
                break

        else:
            encounter_groups.append(
                [signal]
            )

    # =====================================================
    # Attach patient-level evidence
    # =====================================================

    candidates = list(
        encounter_groups
    )

    for (
        key,
        group,
    ) in patient_level_groups.items():

        related_groups = []

        for event_group in encounter_groups:

            if not event_group:
                continue

            event_key = (
                event_group[0].get(
                    "patient_id"
                ),
                _trigger_identity(
                    event_group[0]
                ),
            )

            if event_key == key:
                related_groups.append(
                    event_group
                )

        if len(
            related_groups
        ) == 1:

            # Exactly one matching encounter.
            related_groups[0].extend(
                group
            )

        else:

            # Zero or multiple matching encounters.
            # Preserve patient-level evidence as
            # its own potential.
            candidates.append(
                group
            )

    return [
        _create_candidate(
            group
        )
        for group in candidates
        if group
    ]
