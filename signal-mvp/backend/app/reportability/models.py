from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class ReportabilityInput:
    candidate_id: str
    jurisdiction: Optional[str]
    jurisdiction_status: str
    disease: Optional[str]
    clinical_evidence: dict
    laboratory_evidence: list
    ai_evidence: dict

@dataclass
class ReportabilityAssessment:
    candidate_id: str
    jurisdiction: Optional[str]
    disease: Optional[str]
    decision: str
    evidence_status: str
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
