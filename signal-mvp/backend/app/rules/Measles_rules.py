from dataclasses import dataclass
from typing import List


@dataclass
class RuleResult:
    decision: str
    rule_id: str
    reasons: List[str]
    warnings: List[str]


def _normalize(value: object) -> str:
    """Normalize a laboratory value for rule evaluation."""
    if value is None:
        return ""

    return str(value).strip().casefold()


def _is_positive_lab(lab: dict) -> bool:
    """
    Determine whether a laboratory record contains positive evidence.

    Supports both:
    - canonical SIGNAL fields:
        report_status
        conclusion
        positive

    - legacy evaluator fields:
        status
        result
    """

    # Explicit boolean from the detection layer.
    if lab.get("positive") is True:
        return True

    # Canonical SIGNAL laboratory structure.
    conclusion = _normalize(lab.get("conclusion"))

    positive_terms = (
        "positive",
        "detected",
        "reactive",
        "present",
    )

    if any(term in conclusion for term in positive_terms):
        return True

    # Backward-compatible result field.
    result = _normalize(lab.get("result"))

    if result in {
        "positive",
        "detected",
        "reactive",
        "present",
    }:
        return True

    return False


def _is_negative_lab(lab: dict) -> bool:
    """Determine whether a laboratory record contains negative evidence."""

    result = _normalize(lab.get("result"))
    conclusion = _normalize(lab.get("conclusion"))

    negative_values = {
        "negative",
        "not detected",
        "non-reactive",
        "nonreactive",
        "absent",
    }

    if result in negative_values:
        return True

    if conclusion in negative_values:
        return True

    return False


def _is_pending_lab(lab: dict) -> bool:
    """Determine whether a laboratory result is still pending."""

    status = _normalize(
        lab.get("report_status")
        or lab.get("status")
    )

    result = _normalize(lab.get("result"))
    conclusion = _normalize(lab.get("conclusion"))

    pending_values = {
        "pending",
        "in progress",
        "in_progress",
    }

    return (
        status in pending_values
        or result in pending_values
        or conclusion in pending_values
    )


def _is_inconclusive_lab(lab: dict) -> bool:
    """Determine whether a laboratory result is inconclusive."""

    status = _normalize(
        lab.get("report_status")
        or lab.get("status")
    )

    result = _normalize(lab.get("result"))
    conclusion = _normalize(lab.get("conclusion"))

    inconclusive_values = {
        "inconclusive",
        "indeterminate",
    }

    return (
        status in inconclusive_values
        or result in inconclusive_values
        or conclusion in inconclusive_values
    )


def evaluate_measles_rules(
    disease: str,
    laboratory_evidence: list,
    clinical_evidence: dict,
) -> RuleResult:

    reasons: List[str] = []
    warnings: List[str] = []

    # ---------------------------------------------------------
    # Disease validation
    # ---------------------------------------------------------

    if not disease:
        return RuleResult(
            decision="NEEDS_REVIEW",
            rule_id="MEASLES-001",
            reasons=["Disease is missing."],
            warnings=[],
        )

    if disease.strip().casefold() != "measles":
        return RuleResult(
            decision="NEEDS_REVIEW",
            rule_id="MEASLES-001",
            reasons=[
                "This prototype rule set is configured for measles."
            ],
            warnings=[],
        )

    # ---------------------------------------------------------
    # Laboratory evidence classification
    # ---------------------------------------------------------

    positive_lab = False
    negative_lab = False
    pending_lab = False
    inconclusive_lab = False

    for lab in laboratory_evidence or []:

        if not isinstance(lab, dict):
            continue

        if _is_pending_lab(lab):
            pending_lab = True
            continue

        if _is_inconclusive_lab(lab):
            inconclusive_lab = True
            continue

        if _is_positive_lab(lab):
            positive_lab = True
            continue

        if _is_negative_lab(lab):
            negative_lab = True
            continue

    # ---------------------------------------------------------
    # Decision precedence
    # ---------------------------------------------------------

    # Pending evidence takes precedence over automated reporting.
    if pending_lab:
        return RuleResult(
            decision="HOLD",
            rule_id="MEASLES-002",
            reasons=[
                "Laboratory result is still pending."
            ],
            warnings=[
                "Final reporting decision should wait "
                "for required evidence."
            ],
        )

    # Positive laboratory evidence supports reporting.
    if positive_lab:
        return RuleResult(
            decision="REPORT",
            rule_id="MEASLES-003",
            reasons=[
                "Positive laboratory evidence supports measles."
            ],
            warnings=[],
        )

    # Inconclusive evidence requires human review.
    if inconclusive_lab:
        return RuleResult(
            decision="NEEDS_REVIEW",
            rule_id="MEASLES-004",
            reasons=[
                "Laboratory evidence is inconclusive."
            ],
            warnings=[
                "Manual review is required."
            ],
        )

    # Negative laboratory evidence does not automatically
    # eliminate the candidate.
    if negative_lab:
        return RuleResult(
            decision="NEEDS_REVIEW",
            rule_id="MEASLES-005",
            reasons=[
                "Laboratory result is negative."
            ],
            warnings=[
                "Review clinical and epidemiological evidence."
            ],
        )

    # ---------------------------------------------------------
    # Clinical evidence fallback
    # ---------------------------------------------------------

    symptoms = (
        clinical_evidence.get("symptoms", [])
        if clinical_evidence
        else []
    )

    if symptoms:
        return RuleResult(
            decision="NEEDS_REVIEW",
            rule_id="MEASLES-006",
            reasons=[
                "Clinical evidence is present but laboratory "
                "confirmation is unavailable."
            ],
            warnings=[
                "Additional evidence may be required."
            ],
        )

    # ---------------------------------------------------------
    # Insufficient evidence
    # ---------------------------------------------------------

    return RuleResult(
        decision="NEEDS_REVIEW",
        rule_id="MEASLES-007",
        reasons=[
            "Insufficient evidence for automated decision."
        ],
        warnings=[
            "Manual review required."
        ],
    )