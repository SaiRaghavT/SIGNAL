from typing import Any

from pydantic import BaseModel


class NLPEvidenceRequest(BaseModel):
    documents: list[dict[str, Any]]


class NLPEvidenceResponse(BaseModel):
    evidence: list[dict[str, Any]]
