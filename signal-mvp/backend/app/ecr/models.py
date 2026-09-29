from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ECRPayload:
    ecr_id: str
    case_id: str
    candidate_id: str
    jurisdiction: Optional[str]
    disease: Optional[str]
    patient: Dict[str, Any]
    facility: Dict[str, Any]
    provider: Dict[str, Any]
    clinical_evidence: Dict[str, Any]
    laboratory_evidence: List[Dict[str, Any]]
    ai_evidence: Dict[str, Any]
    reportability_decision: str
    reportability_evidence_status: str
    status: str = "DRAFT"
    warnings: List[str] = field(default_factory=list)
    final_decision: Optional[str] = None
    rule_id: Optional[str] = None
