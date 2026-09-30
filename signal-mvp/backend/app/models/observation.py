from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models.base import Base


class Observation(Base):
    __tablename__ = "observations"

    __table_args__ = (
        UniqueConstraint(
            "source",
            "source_observation_id",
            name="uq_observation_source_id",
        ),
    )

    observation_id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )

    source_observation_id: Mapped[str] = mapped_column(
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

    observation_code: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )

    observation_system: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    observation_display: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    status: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    value_numeric: Mapped[Decimal | None] = mapped_column(
        Numeric,
        nullable=True,
    )

    value_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    unit: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    value_system: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    value_code: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    effective_time: Mapped[datetime | None] = mapped_column(
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