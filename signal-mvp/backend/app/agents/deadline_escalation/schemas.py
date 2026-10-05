from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class DeadlineEscalationRequest(BaseModel):
    case_id: str

    deadline: datetime

    current_time: Optional[datetime] = None

    warning_window_minutes: int = Field(
        default=60,
        gt=0,
    )

    jurisdiction: Optional[str] = None

    rule_id: Optional[str] = None


class DeadlineEscalationResponse(BaseModel):
    escalation_id: str

    case_id: str

    status: str

    urgency: str

    escalation_required: bool

    minutes_remaining: Optional[int] = None

    deadline: datetime

    message: str

    jurisdiction: Optional[str] = None

    rule_id: Optional[str] = None