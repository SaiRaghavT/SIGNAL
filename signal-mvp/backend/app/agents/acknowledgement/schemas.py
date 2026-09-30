from typing import List, Optional

from pydantic import BaseModel, Field


class AcknowledgementRequest(BaseModel):
    submission_id: str


class AcknowledgementResponse(BaseModel):
    submission_id: str
    ecr_id: str
    acknowledgement_id: Optional[str] = None
    pha_case_id: Optional[str] = None
    status: str
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)