from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class SmartFieldResult:
    fields: Dict[str, object] = field(default_factory=dict)
    populated_fields: List[str] = field(default_factory=list)
    missing_fields: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)