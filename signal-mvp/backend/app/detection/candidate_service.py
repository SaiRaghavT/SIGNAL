from __future__ import annotations

from typing import Any, Dict, List

from app.detection.candidate_fusion import fuse_candidate_signals
from app.detection.structured_trigger import detect_structured_triggers


def detect_candidates(
    normalized_patient: Dict[str, Any],
    triggers: List[Dict[str, Any]] | None = None,
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

    signals = detect_structured_triggers(
        normalized_patient,
        triggers=triggers,
    )

    candidates = fuse_candidate_signals(signals)

    return {
        "patient_id": normalized_patient.get("patient", {}).get("id"),
        "signal_count": len(signals),
        "candidate_count": len(candidates),
        "signals": signals,
        "candidates": candidates,
    }