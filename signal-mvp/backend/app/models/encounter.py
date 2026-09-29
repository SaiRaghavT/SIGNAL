from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models.base import Base


class Encounter(Base):
    __tablename__ = "encounters"

    __table_args__ = (
        UniqueConstraint(
            "source",
            "source_encounter_id",
            name="uq_encounter_source_id",
        ),
    )

    encounter_id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )

    source_encounter_id: Mapped[str] = mapped_column(
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

    facility_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    encounter_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    status: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    start_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    end_time: Mapped[datetime | None] = mapped_column(
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