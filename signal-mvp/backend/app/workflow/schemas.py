from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class JourneyStage(BaseModel):
    stage: str
    available: bool
    status: str | None = None
    occurred_at: datetime | None = None
    source: str | None = None
    agent: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)


class CaseJourneyResponse(BaseModel):
    case_id: str
    case_status: str
    disease: str | None = None
    jurisdiction: str | None = None
    current_stage: str
    journey: list[JourneyStage]
    supporting_audit_events: list[dict[str, Any]] = Field(default_factory=list)
    deadline_escalations: list[dict[str, Any]] = Field(default_factory=list)
