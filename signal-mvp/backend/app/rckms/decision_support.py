from dataclasses import dataclass, field
from typing import List
import json

from backend.app.llm.gemini import generate_json
from backend.app.rules.resolver import RuleResolutionError, resolve_rule


@dataclass
class DecisionSupportResult:
    candidate_id: str
    decision: str
    rule_id: str
    reasons: List[str]
    warnings: List[str]
    llm_reasoning: str = ""
    human_review_required: bool = False
    conflicts: List[str] = field(default_factory=list)


def evaluate_decision_support(
    candidate_id: str,
    disease: str,
    laboratory_evidence: list,
    clinical_evidence: dict,
    jurisdiction: str | None = None,
) -> DecisionSupportResult:

    # ---------------------------------------------------------
    # 1. Deterministic RCKMS/rules evaluation
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
        disease=rule.get("disease") or disease,
        laboratory_evidence=laboratory_evidence,
        clinical_evidence=clinical_evidence,
    )

    result = DecisionSupportResult(
        candidate_id=candidate_id,
        decision=rule_result.decision,
        rule_id=rule.get("rule_id") or rule_result.rule_id,
        reasons=list(rule_result.reasons),
        warnings=list(rule_result.warnings),
    )

    # ---------------------------------------------------------
    # 2. Gemini reasoning
    # ---------------------------------------------------------

    prompt = f"""
You are a public-health decision-support assistant.

Analyze the following case using ONLY the supplied information.

Candidate ID:
{candidate_id}

Disease:
{disease}

Jurisdiction:
{jurisdiction or "Not resolved"}

Laboratory evidence:
{json.dumps(laboratory_evidence, indent=2)}

Clinical evidence:
{json.dumps(clinical_evidence, indent=2)}

Deterministic rules decision:
{result.decision}

Rule ID:
{result.rule_id}

Rule reasons:
{json.dumps(result.reasons, indent=2)}

Important:
- Do not invent facts.
- Do not create or change reporting rules.
- Do not override the deterministic rules decision.
- Identify supporting evidence, missing evidence, and conflicts.
- If evidence is insufficient, clearly state that human review may be required.

Return JSON:

{{
    "reasoning": "...",
    "supporting_evidence": [],
    "missing_evidence": [],
    "conflicts": [],
    "human_review_required": false
}}
"""

    llm_reasoning = ""
    human_review_required = False
    conflicts: list[str] = []

    try:
        llm_response = generate_json(prompt)
        llm_result = json.loads(llm_response)

        llm_reasoning = llm_result.get(
            "reasoning",
            "",
        )
        human_review_required = bool(llm_result.get("human_review_required"))
        conflicts = [str(item) for item in llm_result.get("conflicts", [])]

        # Add important LLM findings to warnings
        if human_review_required:
            result.warnings.append(
                "Gemini identified the case for human review."
            )

        for conflict in conflicts:
            result.warnings.append(
                f"LLM conflict: {conflict}"
            )

    except Exception as exc:
        # LLM failure must NOT break deterministic
        # reportability evaluation.
        result.warnings.append(
            f"LLM reasoning unavailable: {exc}"
        )

    # ---------------------------------------------------------
    # 3. Return combined decision-support result
    # ---------------------------------------------------------

    return DecisionSupportResult(
        candidate_id=candidate_id,
        decision=result.decision,
        rule_id=result.rule_id,
        reasons=result.reasons,
        warnings=result.warnings,
        llm_reasoning=llm_reasoning,
        human_review_required=human_review_required,
        conflicts=conflicts,
    )
