from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Float, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models.base import Base


class Candidate(Base):
    __tablename__ = "candidates"
    __table_args__ = (
        UniqueConstraint("detection_key", name="uq_candidates_detection_key"),
    )

    candidate_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    detection_key: Mapped[str] = mapped_column(String(64), nullable=False)
    patient_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    encounter_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    disease_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    jurisdiction: Mapped[str | None] = mapped_column(String(100), nullable=True)
    case_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    detection_source: Mapped[str] = mapped_column(String(100), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    evidence: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    signals: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="POTENTIAL", index=True)
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    severity: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
