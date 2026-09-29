from dataclasses import dataclass
from typing import Dict, List


@dataclass
class RuleResult:
    decision: str
    rule_id: str
    reasons: List[str]
    warnings: List[str]


def evaluate_measles_rules(
    disease: str,
    laboratory_evidence: list,
    clinical_evidence: dict,
) -> RuleResult:

    reasons = []
    warnings = []

    if not disease:
        return RuleResult(
            decision="NEEDS_REVIEW",
            rule_id="MEASLES-001",
            reasons=["Disease is missing."],
            warnings=[]
        )

    if disease.lower() != "measles":
        return RuleResult(
            decision="NEEDS_REVIEW",
            rule_id="MEASLES-001",
            reasons=["This prototype rule set is configured for measles."],
            warnings=[]
        )

    positive_lab = False
    negative_lab = False
    pending_lab = False
    inconclusive_lab = False

    for lab in laboratory_evidence or []:
        status = str(lab.get("status", "")).lower()
        result = str(lab.get("result", "")).lower()

        if status in {"pending", "in_progress"} or result in {"pending", "in progress"}:
            pending_lab = True
        elif status in {"inconclusive", "indeterminate"} or result in {"inconclusive", "indeterminate"}:
            inconclusive_lab = True
        elif result in {"positive", "detected", "reactive"}:
            positive_lab = True

        elif result in {"negative", "not detected", "non-reactive"}:
            negative_lab = True

        elif result in {"pending", "in progress"}:
            pending_lab = True

        elif result in {"inconclusive", "indeterminate"}:
            inconclusive_lab = True

    if pending_lab:
        return RuleResult(
            decision="HOLD",
            rule_id="MEASLES-002",
            reasons=["Laboratory result is still pending."],
            warnings=["Final reporting decision should wait for required evidence."]
        )

    if positive_lab:
        return RuleResult(
            decision="REPORT",
            rule_id="MEASLES-003",
            reasons=["Positive laboratory evidence supports measles."],
            warnings=[]
        )

    if inconclusive_lab:
        return RuleResult(
            decision="NEEDS_REVIEW",
            rule_id="MEASLES-004",
            reasons=["Laboratory evidence is inconclusive."],
            warnings=["Manual review is required."]
        )

    if negative_lab:
        return RuleResult(
            decision="NEEDS_REVIEW",
            rule_id="MEASLES-005",
            reasons=["Laboratory result is negative."],
            warnings=["Review clinical and epidemiological evidence."]
        )

    symptoms = clinical_evidence.get("symptoms", []) if clinical_evidence else []

    if symptoms:
        return RuleResult(
            decision="NEEDS_REVIEW",
            rule_id="MEASLES-006",
            reasons=["Clinical evidence is present but laboratory confirmation is unavailable."],
            warnings=["Additional evidence may be required."]
        )

    return RuleResult(
        decision="NEEDS_REVIEW",
        rule_id="MEASLES-007",
        reasons=["Insufficient evidence for automated decision."],
        warnings=["Manual review required."]
    )