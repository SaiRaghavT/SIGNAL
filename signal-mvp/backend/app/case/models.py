from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

@dataclass
class CaseAssemblyInput:
    candidate_id: str
    patient: Dict[str, Any]
    facility: Dict[str, Any]
    provider: Dict[str, Any]
    disease: Optional[Dict[str, Any]]
    clinical_evidence: Dict[str, Any]
    laboratory_evidence: List[Dict[str, Any]]
    ai_evidence: Dict[str, Any]
    jurisdiction: Optional[str]
    jurisdiction_status: str
    reportability_decision: str
    reportability_evidence_status: str

@dataclass
class SignalCase:
    case_id: str
    candidate_id: str
    patient: Dict[str, Any]
    facility: Dict[str, Any]
    provider: Dict[str, Any]
    disease: Optional[Dict[str, Any]]
    clinical_evidence: Dict[str, Any]
    laboratory_evidence: List[Dict[str, Any]]
    ai_evidence: Dict[str, Any]
    jurisdiction: Optional[str]
    jurisdiction_status: str
    reportability_decision: str
    reportability_evidence_status: str
    status: str
    warnings: List[str] = field(default_factory=list)
