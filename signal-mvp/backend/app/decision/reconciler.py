from backend.app.decision.models import (
    ReconciliationInput,
    ReconciliationResult,
)


def reconcile_decisions(data: ReconciliationInput) -> ReconciliationResult:
    reasons = []
    warnings = []

    ai = (data.ai_decision or "").upper()
    lab = (data.laboratory_decision or "").upper()
    rule = (data.rule_decision or "").upper()

    # ---------------------------------------------------------
    # 1. Human review has highest priority
    # ---------------------------------------------------------
    if data.human_review_required:
        return ReconciliationResult(
            candidate_id=data.candidate_id,
            final_decision="NEEDS_REVIEW",
            reasons=[
                "Human review was requested by decision support."
            ],
            warnings=data.conflicts
            or ["Decision support identified a potential conflict."],
        )

    # ---------------------------------------------------------
    # 2. Jurisdiction must be resolved
    # ---------------------------------------------------------
    if data.jurisdiction_status != "RESOLVED":
        return ReconciliationResult(
            candidate_id=data.candidate_id,
            final_decision="NEEDS_REVIEW",
            reasons=["Jurisdiction is unresolved."],
            warnings=[
                "A resolved jurisdiction is required before reporting."
            ],
        )

    # ---------------------------------------------------------
    # 3. Reportability gate
    # ---------------------------------------------------------
    if data.reportability_decision == "HOLD":
        return ReconciliationResult(
            candidate_id=data.candidate_id,
            final_decision="HOLD",
            reasons=[
                "Reportability assessment placed the candidate on hold."
            ],
            warnings=[
                "Pending evidence must be finalized before reporting."
            ],
        )

    if data.reportability_decision == "NEEDS_REVIEW":
        return ReconciliationResult(
            candidate_id=data.candidate_id,
            final_decision="NEEDS_REVIEW",
            reasons=[
                "Reportability assessment requires review."
            ],
            warnings=[
                "Conflicting or incomplete evidence must be reviewed."
            ],
        )

    # ---------------------------------------------------------
    # 4. Rule decision is the primary reportability decision
    # ---------------------------------------------------------
    if rule == "REPORT":

        reasons.append("Rule engine supports reporting.")

        # Negative laboratory evidence conflicts with the
        # configured reporting rule.
        if lab == "NEGATIVE":
            warnings.append(
                "Laboratory evidence is negative and conflicts "
                "with the reporting rule."
            )

            return ReconciliationResult(
                candidate_id=data.candidate_id,
                final_decision="NEEDS_REVIEW",
                reasons=reasons,
                warnings=warnings,
            )

        # AI disagreement does not override the rule.
        if ai == "NEGATIVE":
            warnings.append(
                "AI decision conflicts with the reporting rule."
            )

        # Positive laboratory evidence supports the rule.
        if lab == "POSITIVE":
            reasons.insert(
                0,
                "Laboratory evidence is positive and supports reporting.",
            )

        return ReconciliationResult(
            candidate_id=data.candidate_id,
            final_decision="REPORT",
            reasons=reasons,
            warnings=warnings,
        )

    # ---------------------------------------------------------
    # 5. Rule says HOLD
    # ---------------------------------------------------------
    if rule == "HOLD":

        if lab == "POSITIVE":
            warnings.append(
                "Positive laboratory evidence conflicts "
                "with the rule-based hold decision."
            )

        if ai == "POSITIVE":
            warnings.append(
                "AI decision conflicts with the rule-based hold decision."
            )

        return ReconciliationResult(
            candidate_id=data.candidate_id,
            final_decision="HOLD",
            reasons=[
                "Rule engine placed the case on hold."
            ],
            warnings=warnings,
        )

    # ---------------------------------------------------------
    # 6. Rule requires review
    # ---------------------------------------------------------
    if rule == "NEEDS_REVIEW":

        return ReconciliationResult(
            candidate_id=data.candidate_id,
            final_decision="NEEDS_REVIEW",
            reasons=[
                "Rule engine requires further review."
            ],
            warnings=[
                "The configured reporting rule did not produce "
                "an automatic reporting decision."
            ],
        )

    # ---------------------------------------------------------
    # 7. Pending / inconclusive laboratory evidence
    # ---------------------------------------------------------
    if lab == "PENDING":
        return ReconciliationResult(
            candidate_id=data.candidate_id,
            final_decision="HOLD",
            reasons=[
                "Laboratory evidence is pending."
            ],
            warnings=[
                "Additional laboratory evidence is required."
            ],
        )

    if lab == "INCONCLUSIVE":
        return ReconciliationResult(
            candidate_id=data.candidate_id,
            final_decision="NEEDS_REVIEW",
            reasons=[
                "Laboratory evidence is inconclusive."
            ],
            warnings=[
                "Additional evidence or human review is required."
            ],
        )

    # ---------------------------------------------------------
    # 8. Negative laboratory evidence without a reporting rule
    # ---------------------------------------------------------
    if lab == "NEGATIVE":
        return ReconciliationResult(
            candidate_id=data.candidate_id,
            final_decision="NEEDS_REVIEW",
            reasons=[
                "Laboratory evidence is negative."
            ],
            warnings=[
                "No applicable rule-based decision was available."
            ],
        )

    # ---------------------------------------------------------
    # 9. Unknown / incomplete evidence
    # ---------------------------------------------------------
    return ReconciliationResult(
        candidate_id=data.candidate_id,
        final_decision="NEEDS_REVIEW",
        reasons=[
            "Evidence does not support an automatic final decision."
        ],
        warnings=warnings,
    )