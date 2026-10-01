from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class SubmissionResult:
    submission_id: Optional[str]
    status: str
    destination: str
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
