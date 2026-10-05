from datetime import datetime, timezone
from typing import Any, Dict, Optional
from datetime import date

from pydantic import BaseModel, Field


class AuditEventCreate(BaseModel):
    entity_type: str
    entity_id: str

    event_type: str

    actor_type: str
    actor_id: str

    source_agent: str

    status: str

    description: Optional[str] = None

    previous_value: Optional[Any] = None
    new_value: Optional[Any] = None

    metadata: Dict[str, Any] = Field(default_factory=dict)
    workflow_stage: str | None = None

    event_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class AuditEventResponse(AuditEventCreate):
    audit_id: str