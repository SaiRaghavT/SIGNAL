from typing import List, Optional

from pydantic import BaseModel, Field


class ECRSubmissionRequest(BaseModel):
    case_id: str


class ECRSubmissionResponse(BaseModel):
    case_id: str
    submission_mode: str | None = None
    report_id: Optional[str] = None
    ecr_id: Optional[str] = None
    submission_id: Optional[str] = None
    status: str
    destination: str
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
