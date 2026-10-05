from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class DeadlineCalculationRequest(BaseModel):
    event_time: datetime

    disease: str

    jurisdiction: str

    rule_id: Optional[str] = None
    candidate_id: str | None = None
    case_id: str | None = None


class DeadlineCalculationResponse(BaseModel):
    deadline: datetime

    calculation_basis: str

    status: str

    disease: str

    jurisdiction: str

    rule_id: Optional[str] = None

    reporting_timing: str

    reporting_method: str
    urgency: str
    minutes_remaining: int