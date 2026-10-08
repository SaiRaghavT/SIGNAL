"""Conservative, catalog-backed evaluator for notifiable conditions."""

from dataclasses import dataclass

from backend.app.rules.resolver import load_catalog


@dataclass
class RuleResult:
    decision: str
    rule_id: str
    reasons: list[str]
    warnings: list[str]


def evaluate_texas_notifiable_rule(
    disease: str,
    laboratory_evidence: list,
    clinical_evidence: dict,
) -> RuleResult:
    """Require review and build the explanation from the configured catalog entry."""
    disease_key = disease.strip().casefold()
    rule = next(
        (
            configured_rule
            for configured_rule in load_catalog().get("rules", [])
            if any(
                str(name).strip().casefold() == disease_key
                for name in [configured_rule.get("disease", ""), *configured_rule.get("aliases", [])]
            )
        ),
        None,
    )
    if rule is None:
        raise ValueError(f"No catalog rule found for disease={disease!r}.")

    reporting = rule.get("reporting", {})
    timeline = reporting.get("timeline_text")
    cases = reporting.get("cases_to_report") or []
    reasons = [f"Applicable reporting rule: {rule['rule_id']}."]
    if cases:
        reasons.append(f"Catalog reporting scope: {', '.join(cases)}.")
    if timeline:
        reasons.append(f"Catalog timeline: {timeline}.")

    warnings = ["Review the evidence and applicable reporting instructions before reporting."]
    destination = reporting.get("destination")
    if destination:
        warnings.append(str(destination))

    return RuleResult(
        decision="NEEDS_REVIEW",
        rule_id=rule["rule_id"],
        reasons=reasons,
        warnings=warnings,
    )
