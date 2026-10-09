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

    if data.jurisdiction_status != "RESOLVED":
        return ReconciliationResult(
            candidate_id=data.candidate_id,
            final_decision="NEEDS_REVIEW",
            reasons=["Jurisdiction is unresolved."],
            warnings=["A resolved jurisdiction is required before reporting."],
        )

    if data.human_review_required or data.conflicts:
        return ReconciliationResult(
            candidate_id=data.candidate_id,
            final_decision="NEEDS_REVIEW",
            reasons=["Human review is required before an automatic decision."],
            warnings=list(data.conflicts),
        )

    reportability = (data.reportability_decision or "").upper()

    if reportability == "HOLD":
        return ReconciliationResult(
            candidate_id=data.candidate_id,
            final_decision="HOLD",
            reasons=["Reportability assessment placed the candidate on hold."],
            warnings=["Pending evidence must be finalized before reporting."],
        )

    if reportability == "NEEDS_REVIEW":
        return ReconciliationResult(
            candidate_id=data.candidate_id,
            final_decision="NEEDS_REVIEW",
            reasons=["Reportability assessment requires review."],
            warnings=["Conflicting or incomplete evidence must be reviewed."],
        )

    if rule == "HOLD":
        if lab == "POSITIVE":
            warnings.append("Positive laboratory evidence conflicts with the rule hold.")
        return ReconciliationResult(
            candidate_id=data.candidate_id,
            final_decision="HOLD",
            reasons=["Rule engine placed the case on hold."],
            warnings=warnings,
        )

    # Strong laboratory evidence takes priority over AI alone.
    if lab == "POSITIVE":
        if ai == "NEGATIVE":
            warnings.append("AI and laboratory decisions conflict.")

        if rule == "NEEDS_REVIEW":
            return ReconciliationResult(
                candidate_id=data.candidate_id,
                final_decision="NEEDS_REVIEW",
                reasons=["Positive laboratory evidence requires rule review."],
                warnings=warnings,
            )

        reasons.append("Laboratory evidence is positive.")

        if rule == "REPORT":
            reasons.append("Rule engine supports reporting.")

        return ReconciliationResult(
            candidate_id=data.candidate_id,
            final_decision="REPORT",
            reasons=reasons,
            warnings=warnings,
        )

    if lab == "NEGATIVE":
        if ai == "POSITIVE":
            warnings.append("AI and laboratory decisions conflict.")

        return ReconciliationResult(
            candidate_id=data.candidate_id,
            final_decision="NEEDS_REVIEW",
            reasons=["Laboratory evidence is negative."],
            warnings=warnings,
        )

    if lab in {"PENDING", "INCONCLUSIVE"}:
        return ReconciliationResult(
            candidate_id=data.candidate_id,
            final_decision="HOLD" if lab == "PENDING" else "NEEDS_REVIEW",
            reasons=[f"Laboratory status is {lab.lower()}."],
            warnings=["Additional evidence or review is required."],
        )

    if rule == "REPORT":
        if ai == "NEGATIVE":
            warnings.append("Rule engine and AI decision conflict.")

        return ReconciliationResult(
            candidate_id=data.candidate_id,
            final_decision="REPORT",
            reasons=["Rule engine supports reporting."],
            warnings=warnings,
        )

    return ReconciliationResult(
        candidate_id=data.candidate_id,
        final_decision="NEEDS_REVIEW",
        reasons=["Evidence does not support an automatic final decision."],
        warnings=warnings,
    )