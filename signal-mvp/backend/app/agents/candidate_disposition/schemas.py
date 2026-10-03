from typing import Any

from pydantic import BaseModel, Field


class CandidateDispositionRequest(BaseModel):
    candidate_id: str
    ai_decision: str | None = None
    ai_confidence: float | None = None
    laboratory_decision: str | None = None
    rule_decision: str | None = None
    jurisdiction_status: str = "RESOLVED"
    reportability_decision: str | None = None
    human_review_required: bool = False
    conflicts: list[Any] = Field(default_factory=list)


class CandidateDispositionResponse(BaseModel):
    candidate_id: str
    final_decision: str
    reasons: list[str]
    warnings: list[str]
