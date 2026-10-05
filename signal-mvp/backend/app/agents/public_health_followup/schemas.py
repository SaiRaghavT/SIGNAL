from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field


class PublicHealthFollowupRequest(BaseModel):
    case_id: str
    submission_id: str | None = None
    action: str = Field(
        ...,
        description=(
            "Follow-up action such as "
            "REQUEST_INFORMATION, INVESTIGATION, "
            "OUTCOME_UPDATE, or CLOSE."
        ),
    )
    notes: Optional[str] = None
    next_action: str | None = None
    due_date: date | None = None


class PublicHealthFollowupResponse(BaseModel):
    case_id: str
    status: str
    action: str
    followup_id: str
    submission_id: str | None = None
    patient_id: str | None = None
    disease: str | None = None
    next_action: str | None = None
    due_date: date | None = None
    notes: Optional[str] = None
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)