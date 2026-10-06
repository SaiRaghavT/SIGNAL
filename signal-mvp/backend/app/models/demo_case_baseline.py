from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models.base import Base


class DemoCaseBaseline(Base):
    """Initial SIGNAL demo workflow values needed for a repeatable local reset."""

    __tablename__ = "demo_case_baselines"

    case_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    case_state: Mapped[dict] = mapped_column(JSONB, nullable=False)
    candidate_state: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
