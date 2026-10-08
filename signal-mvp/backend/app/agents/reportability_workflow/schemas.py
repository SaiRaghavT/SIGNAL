from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class CandidateProcessRequest(BaseModel):
    candidate_id: str

    model_config = {"extra": "forbid"}


class CandidateWorkflowInput(BaseModel):
    candidate_id: str
    existing_case_id: str | None = None
    # Canonical patient UUID. If omitted, candidate_id must itself be a UUID
    # for compatibility with detection flows that use the patient UUID as ID.
    patient_id: UUID | None = None
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

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_lab_evidence(cls, value: Any) -> Any:
        """Accept the older singular ``lab_evidence`` request shape."""
        if not isinstance(value, dict):
            return value

        normalized = dict(value)
        if "laboratory_evidence" not in normalized and "lab_evidence" in normalized:
            normalized["laboratory_evidence"] = normalized.pop("lab_evidence")

        labs = normalized.get("laboratory_evidence")
        if isinstance(labs, dict):
            normalized["laboratory_evidence"] = [labs]

        return normalized


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
