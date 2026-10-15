from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class DeadlineCalculationRequest(BaseModel):
    event_time: datetime

    disease: str | None = None

    jurisdiction: str

    rule_id: Optional[str] = None
    reporting_scope: str = "CASE_REPORT"
    candidate_id: str | None = None
    case_id: str | None = None


class DeadlineCalculationResponse(BaseModel):
    deadline: datetime | None = None

    calculation_basis: str

    status: str

    disease: str | None = None

    jurisdiction: str

    rule_id: Optional[str] = None

    reporting_timing: str | None = None

    reporting_method: str | None = None
    urgency: str | None = None
    minutes_remaining: int | None = None
    is_immediate: bool = False
    effective_year: int | None = None
    source_url: str | None = None
    applicability: str | None = None
