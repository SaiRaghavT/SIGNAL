from dataclasses import dataclass, field
import json
from typing import Any, List

from backend.app.config.settings import settings
from backend.app.rules.resolver import (
    RuleResolutionError,
    resolve_rule,
)


@dataclass
class DecisionSupportResult:
    candidate_id: str
    decision: str
    rule_id: str
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    llm_reasoning: str = ""
    supporting_evidence: List[Any] = field(default_factory=list)
    missing_evidence: List[Any] = field(default_factory=list)
    conflicts: List[Any] = field(default_factory=list)
    human_review_required: bool = False


def evaluate_decision_support(
    candidate_id: str,
    disease: str,
    jurisdiction: str,
    laboratory_evidence: list,
    clinical_evidence: dict,
) -> DecisionSupportResult:
    """
    Agent 21 - RCKMS/eCR Decision Support.

    Agent 21 is disease- and jurisdiction-agnostic.

    The applicable reporting rule is resolved through the
    external rule catalog and resolver. Agent 21 itself
    does not contain disease-specific reporting logic.
    """

    # ---------------------------------------------------------
    # 1. Resolve applicable reporting rule
    # ---------------------------------------------------------

    try:
        rule = resolve_rule(
            disease=disease,
            jurisdiction=jurisdiction,
        )

    except RuleResolutionError as exc:
        return DecisionSupportResult(
            candidate_id=candidate_id,
            decision="NEEDS_REVIEW",
            rule_id="NO_RULE_AVAILABLE",
            reasons=[
                "No applicable reporting rule could be resolved."
            ],
            warnings=[
                str(exc),
                "Human review is required.",
            ],
            human_review_required=True,
        )

    # ---------------------------------------------------------
    # 2. Evaluate the resolved deterministic rule
    # ---------------------------------------------------------

    evaluator = rule["evaluator"]

    rule_result = evaluator(
        disease=disease,
        laboratory_evidence=laboratory_evidence,
        clinical_evidence=clinical_evidence,
    )

    result = DecisionSupportResult(
        candidate_id=candidate_id,
        decision=rule_result.decision,
        rule_id=rule_result.rule_id,
        reasons=list(rule_result.reasons),
        warnings=list(rule_result.warnings),
    )

    # ---------------------------------------------------------
    # 3. Optional LLM reasoning
    # ---------------------------------------------------------

    prompt = f"""
You are a public-health decision-support assistant.

Analyze the supplied case using ONLY the supplied information.

Candidate ID:
{candidate_id}

Disease:
{disease}

Jurisdiction:
{jurisdiction}

Resolved rule:
{rule.get("rule_id")}

Rule version:
{rule.get("rule_version")}

Laboratory evidence:
{json.dumps(laboratory_evidence, indent=2, default=str)}

Clinical evidence:
{json.dumps(clinical_evidence, indent=2, default=str)}

Deterministic rule decision:
{result.decision}

Deterministic rule ID:
{result.rule_id}

Rule reasons:
{json.dumps(result.reasons, indent=2, default=str)}

Important:
- Do not invent facts.
- Do not create reporting rules.
- Do not modify reporting rules.
- Do not override the deterministic rule decision.
- Identify supporting evidence.
- Identify missing evidence.
- Identify conflicts.
- If evidence is insufficient, indicate that human review may be required.

Return JSON:

{{
    "reasoning": "",
    "supporting_evidence": [],
    "missing_evidence": [],
    "conflicts": [],
    "human_review_required": false
}}
"""

    # ---------------------------------------------------------
    # 4. Deterministic-only mode
    # ---------------------------------------------------------

    if not settings.gemini_enabled:
        result.warnings.append(
            "LLM reasoning is disabled; deterministic rules were used."
        )
        return result

    # ---------------------------------------------------------
    # 5. Optional Gemini reasoning
    # ---------------------------------------------------------

    try:
        from backend.app.llm.gemini import generate_json

        llm_response = generate_json(prompt)

        if isinstance(llm_response, str):
            llm_result = json.loads(llm_response)
        else:
            llm_result = llm_response

        result.llm_reasoning = llm_result.get(
            "reasoning",
            "",
        )

        result.supporting_evidence = llm_result.get(
            "supporting_evidence",
            [],
        )

        result.missing_evidence = llm_result.get(
            "missing_evidence",
            [],
        )

        result.conflicts = llm_result.get(
            "conflicts",
            [],
        )

        result.human_review_required = bool(
            llm_result.get(
                "human_review_required",
                False,
            )
        )

        if result.human_review_required:
            result.warnings.append(
                "LLM identified that human review may be required."
            )

        for conflict in result.conflicts:
            result.warnings.append(
                f"Evidence conflict: {conflict}"
            )

    except Exception as exc:
        # LLM failure must never prevent deterministic evaluation.
        result.warnings.append(
            f"LLM reasoning unavailable: {exc}"
        )

    return result