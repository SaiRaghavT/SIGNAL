from typing import Any

from pydantic import BaseModel


class DocumentIntelligenceRequest(BaseModel):
    documents: list[dict[str, Any]]


class DocumentIntelligenceResponse(BaseModel):
    documents: list[dict[str, Any]]
