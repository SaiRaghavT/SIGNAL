from dataclasses import dataclass
from typing import List
import json

from backend.app.rules.Measles_rules import evaluate_measles_rules
from backend.app.llm.gemini import generate_json


@dataclass
class DecisionSupportResult:
    candidate_id: str
    decision: str
    rule_id: str
    reasons: List[str]
    warnings: List[str]
    llm_reasoning: str = ""


def evaluate_decision_support(
    candidate_id: str,
    disease: str,
    laboratory_evidence: list,
    clinical_evidence: dict,
) -> DecisionSupportResult:

    # ---------------------------------------------------------
    # 1. Deterministic RCKMS/rules evaluation
    # ---------------------------------------------------------

    result = evaluate_measles_rules(
        disease=disease,
        laboratory_evidence=laboratory_evidence,
        clinical_evidence=clinical_evidence,
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

    try:
        llm_response = generate_json(prompt)
        llm_result = json.loads(llm_response)

        llm_reasoning = llm_result.get(
            "reasoning",
            "",
        )

        # Add important LLM findings to warnings
        if llm_result.get("human_review_required"):
            result.warnings.append(
                "Gemini identified the case for human review."
            )

        for conflict in llm_result.get("conflicts", []):
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
    )