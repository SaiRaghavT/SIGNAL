from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class FormRenderingRequest(BaseModel):
    case_id: str

    form_id: str

    form_version: Optional[str] = None

    report_data: Dict[str, Any] = Field(
        default_factory=dict
    )


class RenderedField(BaseModel):
    field: str

    value: Any = None

    source: Optional[str] = None

    confidence: Optional[float] = None

    status: str


class FormRenderingResponse(BaseModel):
    case_id: str

    form_id: str

    form_version: Optional[str] = None

    status: str

    fields: List[RenderedField] = Field(
        default_factory=list
    )

    populated_fields: List[str] = Field(
        default_factory=list
    )

    missing_fields: List[str] = Field(
        default_factory=list
    )

    warnings: List[str] = Field(
        default_factory=list
    )

    rendered_document: Optional[str] = None