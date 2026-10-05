from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ManualReportingRequest(BaseModel):
    case_id: str

    reporting_method: str = Field(
        ...,
        description=(
            "Manual reporting method, such as "
            "FORM, FAX, PHONE, or SECURE_EMAIL."
        ),
    )

    notes: Optional[str] = None


class ManualReportingResponse(BaseModel):
    case_id: str

    status: str

    reporting_method: str

    jurisdiction: Optional[str] = None

    disease: Optional[str] = None

    form_id: Optional[str] = None

    form_version: Optional[str] = None

    report_data: Dict[str, Any] = Field(
        default_factory=dict
    )

    missing_fields: List[str] = Field(
        default_factory=list
    )

    warnings: List[str] = Field(
        default_factory=list
    )

    notes: Optional[str] = None