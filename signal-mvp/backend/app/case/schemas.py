from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CaseListItem(BaseModel):
    case_id: str
    candidate_id: str
    disease: str | None = None
    jurisdiction: str | None = None
    status: str
    reportability_decision: str
    final_decision: str | None = None
    rule_id: str | None = None
    created_at: datetime
    updated_at: datetime
    warnings: list[Any] = Field(default_factory=list)


class CaseListResponse(BaseModel):
    items: list[CaseListItem]
    total: int
    page: int
    page_size: int


class CaseDetailResponse(BaseModel):
    case_id: str
    candidate_id: str
    disease: str | None = None
    jurisdiction: str | None = None
    jurisdiction_status: str
    status: str
    reportability_decision: str
    reportability_evidence_status: str
    final_decision: str | None = None
    rule_id: str | None = None
    warnings: list[Any] = Field(default_factory=list)
    patient: dict[str, Any]
    facility: dict[str, Any]
    provider: dict[str, Any]
    clinical_evidence: dict[str, Any]
    laboratory_evidence: list[Any]
    ai_evidence: dict[str, Any]
    report_fields: dict[str, Any] = Field(default_factory=dict)
    missing_report_fields: list[str] = Field(default_factory=list)
    required_missing_fields: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class CaseReportUpdateRequest(BaseModel):
    report_fields: dict[str, Any] = Field(default_factory=dict)
    provider: dict[str, Any] | None = None
    facility: dict[str, Any] | None = None
    reviewer_id: str = "reporting_user"


class CaseReportUpdateResponse(BaseModel):
    case_id: str
    report_fields: dict[str, Any]
    provider: dict[str, Any]
    facility: dict[str, Any]
    missing_report_fields: list[str]
    required_missing_fields: list[str]
    validation: dict[str, Any]
