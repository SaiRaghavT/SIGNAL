from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class SmartFieldResult:
    fields: Dict[str, Any] = field(default_factory=dict)

    populated_fields: List[str] = field(default_factory=list)

    missing_fields: List[str] = field(default_factory=list)

    required_missing_fields: List[str] = field(default_factory=list)

    sources: Dict[str, str] = field(default_factory=dict)

    confidence: Dict[str, float] = field(default_factory=dict)

    warnings: List[str] = field(default_factory=list)