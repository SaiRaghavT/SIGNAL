from __future__ import annotations

from typing import Any, Dict, List

from backend.app.detection.candidate_fusion import fuse_candidate_signals
from backend.app.detection.document_trigger import detect_document_triggers
from backend.app.detection.structured_trigger import detect_structured_triggers


def detect_candidates(
    normalized_patient: Dict[str, Any],
    triggers: List[Dict[str, Any]] | None = None,
    document_evidence: List[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    """
    Run the SIGNAL structured candidate detection pipeline.

    Flow:
        Normalized Patient
            ↓
        Structured Trigger Detection
            ↓
        Candidate Signals
            ↓
        Candidate Fusion
            ↓
        Potential Candidates

    This service does not determine:
        - jurisdiction
        - reportability
        - case confirmation
        - submission
    """

    if not isinstance(normalized_patient, dict):
        raise ValueError("normalized_patient must be a dictionary.")

    # ---------------------------------------------------------
    # Structured detection
    # ---------------------------------------------------------

    signals = detect_structured_triggers(
        normalized_patient,
        triggers=triggers,
    )

    # Keep source-note records visible as document signals, but don't let a
    # note with no disease match create an extra potential disease candidate.
    source_document_signals = [
        signal
        for signal in signals
        if (signal.get("evidence") or {}).get("evidence_role")
        == "supporting_clinical_evidence"
    ]
    structured_signals = [
        signal for signal in signals if signal not in source_document_signals
    ]

    # ---------------------------------------------------------
    # Document detection
    # ---------------------------------------------------------

    document_evidence_signals = detect_document_triggers(
        document_evidence or [],
        patient_id=str(
            normalized_patient.get("patient", {}).get("id") or ""
        ),
        structured_signals=structured_signals,
    )

    # ---------------------------------------------------------
    # Combine signals
    # ---------------------------------------------------------

    candidate_signals = structured_signals + document_evidence_signals
    all_signals = candidate_signals + source_document_signals

    # ---------------------------------------------------------
    # Signal counts
    # ---------------------------------------------------------

    condition_signal_count = sum(
        1
        for signal in structured_signals
        if signal.get("trigger_type") == "SUSPECTED_DISORDER"
    )

    lab_signal_count = sum(
        1
        for signal in structured_signals
        if signal.get("trigger_type") == "LAB_RESULT"
    )

    # ---------------------------------------------------------
    # Candidate fusion
    # ---------------------------------------------------------

    candidates = fuse_candidate_signals(candidate_signals)

    # Attach source notes to the disease candidate for review. Source-note
    # signals stay out of fusion above, so they can enrich a real candidate
    # without becoming generic "Potential condition" cards themselves.
    if len(candidates) == 1:
        candidates[0]["signals"].extend(source_document_signals)
        candidates[0]["evidence"].extend(
            signal.get("evidence", {}) for signal in source_document_signals
        )
        candidates[0]["trigger_types"] = list(
            dict.fromkeys(
                [*(candidates[0].get("trigger_types") or []), "DOCUMENT_EVIDENCE"]
            )
        )
        candidates[0]["evidence_source_types"] = list(
            dict.fromkeys(
                [
                    *(candidates[0].get("evidence_source_types") or []),
                    "document",
                ]
            )
        )
        candidates[0]["supporting_signal_count"] = len(candidates[0]["signals"])
    elif candidates:
        for document_signal in source_document_signals:
            document_evidence = document_signal.get("evidence") or {}
            source_id = document_evidence.get("source_id")
            encounter_id = document_signal.get("encounter_id")
            matching_candidates = [
                candidate
                for candidate in candidates
                if any(
                    (signal.get("evidence") or {}).get("source_id") == source_id
                    for signal in candidate.get("signals", [])
                )
                or (
                    encounter_id is not None
                    and candidate.get("encounter_id") == encounter_id
                )
            ]
            if len(matching_candidates) == 1:
                candidate = matching_candidates[0]
                candidate["signals"].append(document_signal)
                candidate["evidence"].append(document_evidence)
                candidate["supporting_signal_count"] = len(candidate["signals"])

    # ---------------------------------------------------------
    # Response
    # ---------------------------------------------------------

    return {
        "patient_id": normalized_patient.get("patient", {}).get("id"),

        # Total signal count
        "signal_count": len(all_signals),

        # Structured signal breakdown
        "structured_signal_count": len(structured_signals),
        "condition_signal_count": condition_signal_count,
        "lab_signal_count": lab_signal_count,

        # Document signal count
        "document_signal_count": len(source_document_signals),
        "document_signals": source_document_signals,
        "document_evidence_signal_count": len(document_evidence_signals),

        # Candidates
        "candidate_count": len(candidates),

        "signals": all_signals,
        "candidates": candidates,
    }
