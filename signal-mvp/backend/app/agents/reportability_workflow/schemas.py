from typing import Any

from pydantic import BaseModel, Field


class CandidateProcessRequest(BaseModel):
    candidate_id: str
    patient_state: str | None = None
    patient_county: str | None = None
    facility_state: str | None = None
    facility_county: str | None = None
    disease: str | None = None
    patient: dict[str, Any] = Field(default_factory=dict)
    provider: dict[str, Any] = Field(default_factory=dict)
    facility: dict[str, Any] = Field(default_factory=dict)
    clinical_evidence: dict[str, Any] = Field(default_factory=dict)
    laboratory_evidence: list[dict[str, Any]] = Field(default_factory=list)
    ai_evidence: dict[str, Any] = Field(default_factory=dict)


class CandidateProcessResponse(BaseModel):
    candidate_id: str
    workflow_status: str
    jurisdiction: dict[str, Any]
    reportability: dict[str, Any]
    rule_evaluation: dict[str, Any]
    reconciliation: dict[str, Any]
    smart_field_population: dict[str, Any]
    case: dict[str, Any]
    ecr: dict[str, Any]
    validation: dict[str, Any]
    submission: dict[str, Any]
