from typing import List, Optional

from pydantic import BaseModel, Field


class RetryResubmissionRequest(BaseModel):
    submission_id: str
    reason: Optional[str] = None


class RetryResubmissionResponse(BaseModel):
    submission_id: str
    case_id: str
    ecr_id: str
    status: str
    retry_count: int
    new_submission_id: Optional[str] = None
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)