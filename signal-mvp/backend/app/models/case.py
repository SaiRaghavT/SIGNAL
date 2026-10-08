from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models.base import Base


class Case(Base):
    __tablename__ = "cases"
    __table_args__ = (
        UniqueConstraint("candidate_id", name="uq_cases_candidate_id"),
    )

    case_id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )

    candidate_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    patient: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
    )

    facility: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
    )

    provider: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
    )

    disease: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )

    clinical_evidence: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
    )

    laboratory_evidence: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
    )

    ai_evidence: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
    )

    report_fields: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    jurisdiction: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )

    jurisdiction_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    reportability_decision: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    reportability_evidence_status: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    # Shared reporting mode selected before this case enters the submission queue.
    submission_mode: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)

    final_decision: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    rule_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    deadline: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    severity: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        index=True,
    )

    warnings: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
