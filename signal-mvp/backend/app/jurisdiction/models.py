from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class JurisdictionInput:
    candidate_id: str
    patient_state: Optional[str]
    patient_county: Optional[str]
    facility_state: Optional[str]
    facility_county: Optional[str]
    disease: Optional[str]

@dataclass
class JurisdictionResult:
    candidate_id: str
    jurisdiction: Optional[str]
    status: str
    reasons: List[str] = field(default_factory=list)
