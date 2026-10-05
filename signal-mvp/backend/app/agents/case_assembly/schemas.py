from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CaseAssemblyRequest(BaseModel):
    patient_id: str

    candidate_signals: List[Dict[str, Any]] = Field(
        default_factory=list
    )

    reportability_decision: Optional[Dict[str, Any]] = None

    jurisdiction: Optional[str] = None

    reporting_deadline: Optional[str] = None


class CaseAssemblyResponse(BaseModel):
    case_reference: str

    patient_id: str

    status: str

    jurisdiction: Optional[str] = None

    candidate_signals: List[Dict[str, Any]]

    reportability_decision: Optional[Dict[str, Any]] = None

    reporting_deadline: Optional[str] = None

    assembled_data: Dict[str, Any]