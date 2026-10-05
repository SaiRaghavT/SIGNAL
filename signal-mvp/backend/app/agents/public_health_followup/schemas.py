from typing import List, Optional

from pydantic import BaseModel, Field


class PublicHealthFollowupRequest(BaseModel):
    case_id: str
    action: str = Field(
        ...,
        description=(
            "Follow-up action such as "
            "REQUEST_INFORMATION, INVESTIGATION, "
            "OUTCOME_UPDATE, or CLOSE."
        ),
    )
    notes: Optional[str] = None


class PublicHealthFollowupResponse(BaseModel):
    case_id: str
    status: str
    action: str
    followup_id: str
    notes: Optional[str] = None
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)