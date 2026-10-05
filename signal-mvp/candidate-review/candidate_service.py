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

    signals = detect_structured_triggers(
        normalized_patient,
        triggers=triggers,
    )

    document_signals = detect_document_triggers(
        document_evidence or [],
        patient_id=str(normalized_patient.get("patient", {}).get("id") or ""),
    )
    all_signals = signals + document_signals
    candidates = fuse_candidate_signals(all_signals)

    return {
        "patient_id": normalized_patient.get("patient", {}).get("id"),
        "signal_count": len(all_signals),
        "structured_signal_count": len(signals),
        "document_signal_count": len(document_signals),
        "candidate_count": len(candidates),
        "signals": all_signals,
        "candidates": candidates,
    }
