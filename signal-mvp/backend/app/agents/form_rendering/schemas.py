from typing import Any, List, Optional

from pydantic import BaseModel, Field


class FormRenderingRequest(BaseModel):
    case_id: str

    form_id: str

    form_version: Optional[str] = None

    field_values: dict[str, Any] = Field(default_factory=dict)


class RenderedField(BaseModel):
    field: str

    value: Any = None

    source: Optional[str] = None

    confidence: Optional[float] = None

    status: str


class FormRenderingResponse(BaseModel):
    case_id: str

    form_id: Optional[str] = None

    report_id: Optional[str] = None

    render_id: Optional[str] = None

    retrieval_url: Optional[str] = None

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

    missing_required_fields: List[str] = Field(default_factory=list)

    demo_mode: bool = False

    warnings: List[str] = Field(
        default_factory=list
    )

    rendered_document: Optional[str] = None


class FormFieldDefinition(BaseModel):
    field: str
    source: str | None = None
    required: bool = False


class FormDefinitionResponse(BaseModel):
    form_id: str
    form_version: str
    disease: str
    jurisdiction: str
    fields: List[FormFieldDefinition] = Field(default_factory=list)
