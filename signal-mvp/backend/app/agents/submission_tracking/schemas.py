from typing import List, Optional

from pydantic import BaseModel, Field


class SubmissionTrackingRequest(BaseModel):
    submission_id: str


class SubmissionTrackingResponse(BaseModel):
    submission_id: str
    case_id: str
    ecr_id: str
    status: str
    destination: str
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)