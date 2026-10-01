from dataclasses import dataclass, field
from typing import Any, List, Optional


@dataclass
class ReconciliationInput:
    candidate_id: str
    ai_decision: Optional[str]
    ai_confidence: Optional[float]
    laboratory_decision: Optional[str]
    rule_decision: Optional[str]
    jurisdiction_status: str = "RESOLVED"
    reportability_decision: Optional[str] = None
    human_review_required: bool = False
    conflicts: List[Any] = field(default_factory=list)


@dataclass
class ReconciliationResult:
    candidate_id: str
    final_decision: str
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)