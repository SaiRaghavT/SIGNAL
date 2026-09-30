from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models.base import Base


class Condition(Base):
    __tablename__ = "conditions"

    __table_args__ = (
        UniqueConstraint(
            "source",
            "source_condition_id",
            name="uq_condition_source_id",
        ),
    )

    condition_id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )

    source_condition_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    patient_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "patients.patient_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    encounter_id: Mapped[UUID | None] = mapped_column(
        ForeignKey(
            "encounters.encounter_id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    condition_code: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )

    condition_system: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    condition_display: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    clinical_status: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    verification_status: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    onset_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    recorded_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    source: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    source_resource: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
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