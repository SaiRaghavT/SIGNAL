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

    # ---------------------------------------------------------
    # Document detection
    # ---------------------------------------------------------

    document_signals = detect_document_triggers(
        document_evidence or [],
        patient_id=str(
            normalized_patient.get("patient", {}).get("id") or ""
        ),
    )

    # ---------------------------------------------------------
    # Combine signals
    # ---------------------------------------------------------

    all_signals = signals + document_signals

    # ---------------------------------------------------------
    # Signal counts
    # ---------------------------------------------------------

    condition_signal_count = sum(
        1
        for signal in signals
        if signal.get("trigger_type") == "SUSPECTED_DISORDER"
    )

    lab_signal_count = sum(
        1
        for signal in signals
        if signal.get("trigger_type") == "LAB_RESULT"
    )

    # ---------------------------------------------------------
    # Candidate fusion
    # ---------------------------------------------------------

    candidates = fuse_candidate_signals(all_signals)

    # ---------------------------------------------------------
    # Response
    # ---------------------------------------------------------

    return {
        "patient_id": normalized_patient.get("patient", {}).get("id"),

        # Total signal count
        "signal_count": len(all_signals),

        # Structured signal breakdown
        "structured_signal_count": len(signals),
        "condition_signal_count": condition_signal_count,
        "lab_signal_count": lab_signal_count,

        # Document signal count
        "document_signal_count": len(document_signals),

        # Candidates
        "candidate_count": len(candidates),

        "signals": all_signals,
        "candidates": candidates,
    }