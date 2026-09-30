from backend.app.decision.models import ReconciliationInput
from backend.app.decision.reconciler import reconcile_decisions


def test_report_when_rule_and_lab_support_reporting():
    result = reconcile_decisions(
        ReconciliationInput(
            candidate_id="TEST-REPORT",
            ai_decision=None,
            ai_confidence=None,
            laboratory_decision="POSITIVE",
            rule_decision="REPORT",
            jurisdiction_status="RESOLVED",
            reportability_decision="PROCEED_TO_RULES",
        )
    )

    assert result.final_decision == "REPORT"


def test_hold_when_rule_says_hold():
    result = reconcile_decisions(
        ReconciliationInput(
            candidate_id="TEST-HOLD",
            ai_decision=None,
            ai_confidence=None,
            laboratory_decision="POSITIVE",
            rule_decision="HOLD",
            jurisdiction_status="RESOLVED",
            reportability_decision="PROCEED_TO_RULES",
        )
    )

    assert result.final_decision == "HOLD"
    assert any("conflicts" in warning.lower() for warning in result.warnings)


def test_needs_review_when_rule_requires_review():
    result = reconcile_decisions(
        ReconciliationInput(
            candidate_id="TEST-REVIEW",
            ai_decision=None,
            ai_confidence=None,
            laboratory_decision="POSITIVE",
            rule_decision="NEEDS_REVIEW",
            jurisdiction_status="RESOLVED",
            reportability_decision="PROCEED_TO_RULES",
        )
    )

    assert result.final_decision == "NEEDS_REVIEW"


def test_negative_lab_conflicts_with_report_rule():
    result = reconcile_decisions(
        ReconciliationInput(
            candidate_id="TEST-LAB-CONFLICT",
            ai_decision=None,
            ai_confidence=None,
            laboratory_decision="NEGATIVE",
            rule_decision="REPORT",
            jurisdiction_status="RESOLVED",
            reportability_decision="PROCEED_TO_RULES",
        )
    )

    assert result.final_decision == "NEEDS_REVIEW"


def test_ai_conflict_does_not_override_rule():
    result = reconcile_decisions(
        ReconciliationInput(
            candidate_id="TEST-AI-CONFLICT",
            ai_decision="NEGATIVE",
            ai_confidence=0.95,
            laboratory_decision="POSITIVE",
            rule_decision="REPORT",
            jurisdiction_status="RESOLVED",
            reportability_decision="PROCEED_TO_RULES",
        )
    )

    assert result.final_decision == "REPORT"
    assert any("AI" in warning for warning in result.warnings)


def test_unresolved_jurisdiction_requires_review():
    result = reconcile_decisions(
        ReconciliationInput(
            candidate_id="TEST-JURISDICTION",
            ai_decision=None,
            ai_confidence=None,
            laboratory_decision="POSITIVE",
            rule_decision="REPORT",
            jurisdiction_status="UNRESOLVED",
            reportability_decision="PROCEED_TO_RULES",
        )
    )

    assert result.final_decision == "NEEDS_REVIEW"


def test_human_review_overrides_automatic_decision():
    result = reconcile_decisions(
        ReconciliationInput(
            candidate_id="TEST-HUMAN-REVIEW",
            ai_decision="POSITIVE",
            ai_confidence=0.95,
            laboratory_decision="POSITIVE",
            rule_decision="REPORT",
            jurisdiction_status="RESOLVED",
            reportability_decision="PROCEED_TO_RULES",
            human_review_required=True,
            conflicts=["Evidence conflict detected"],
        )
    )

    assert result.final_decision == "NEEDS_REVIEW"
    assert "Evidence conflict detected" in result.warnings