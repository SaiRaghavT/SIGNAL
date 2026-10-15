from typing import Literal

from pydantic import BaseModel, Field


SubmissionMode = Literal["IMMEDIATE", "INDIVIDUAL", "BATCH"]


class QueueRequest(BaseModel):
    actor_id: str = Field(min_length=1, max_length=255)
    submission_mode: SubmissionMode | None = None
    demo_submission: bool = False
    demo_review_confirmed: bool = False


class BatchCreateRequest(BaseModel):
    case_ids: list[str] = Field(min_length=1, max_length=100)
    actor_id: str = Field(min_length=1, max_length=255)


class AdminReviewRequest(BaseModel):
    reviewer_id: str = Field(min_length=1, max_length=255)
    reviewer_role: str = Field(min_length=1, max_length=100)
    decision: Literal["APPROVE", "REQUEST_INFORMATION", "REJECT"]
    comments: str | None = None


class AdminSessionSubmissionCleanupRequest(BaseModel):
    submission_ids: list[str] = Field(max_length=500)
