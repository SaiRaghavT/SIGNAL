from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CandidateResponse(BaseModel):
    candidate_id: str
    patient_id: str
    patient: dict[str, Any]
    disease: str
    jurisdiction: str | None = None
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float | None = None
    status: str
    case_id: str | None = None
    created_at: datetime
    updated_at: datetime


class CandidateListResponse(BaseModel):
    items: list[CandidateResponse]
    page: int
    page_size: int
    total: int
    pages: int


class CandidateDispositionUpdate(BaseModel):
    ai_decision: str | None = None
    ai_confidence: float | None = None
    laboratory_decision: str | None = None
    rule_decision: str | None = None
    jurisdiction_status: str = "RESOLVED"
    reportability_decision: str | None = None
    human_review_required: bool = False
    conflicts: list[Any] = Field(default_factory=list)


class CandidateDispositionResult(BaseModel):
    candidate_id: str
    final_decision: str
    reasons: list[str]
    warnings: list[str]
    status: str
