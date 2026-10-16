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
    confidence: float | None = Field(default=None, ge=0, le=1)
    confidence_method: str = "unavailable"
    confidence_components: list[dict[str, Any]] = Field(default_factory=list)
    evidence_strength: float | None = Field(default=None, ge=0, le=100)
    evidence_strength_method: str = "unavailable"
    evidence_strength_components: list[dict[str, Any]] = Field(default_factory=list)
    primary_trigger: dict[str, Any] | None = None
    detection_priority: str = "STANDARD"
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
