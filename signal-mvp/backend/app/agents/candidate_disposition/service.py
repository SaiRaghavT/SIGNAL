from backend.app.decision.models import ReconciliationInput, ReconciliationResult
from backend.app.decision.reconciler import reconcile_decisions

from .schemas import CandidateDispositionRequest


def determine_candidate_disposition(
    request: CandidateDispositionRequest,
) -> ReconciliationResult:
    """Determine the candidate outcome from rule, evidence, and review signals."""

    return reconcile_decisions(
        ReconciliationInput(
            candidate_id=request.candidate_id,
            ai_decision=request.ai_decision,
            ai_confidence=request.ai_confidence,
            laboratory_decision=request.laboratory_decision,
            rule_decision=request.rule_decision,
            jurisdiction_status=request.jurisdiction_status,
            reportability_decision=request.reportability_decision,
            human_review_required=request.human_review_required,
            conflicts=request.conflicts,
        )
    )
