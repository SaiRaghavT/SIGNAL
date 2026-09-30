from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    String,
    Table,
    Text,
    UniqueConstraint,
    UUID as SQLAlchemyUUID,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.base import Base


# Association table:
# One LabResult can be linked to multiple Observations.
lab_result_observations = Table(
    "lab_result_observations",
    Base.metadata,
    Column(
        "lab_result_id",
        SQLAlchemyUUID(as_uuid=True),
        ForeignKey(
            "lab_results.lab_result_id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    ),
    Column(
        "observation_id",
        SQLAlchemyUUID(as_uuid=True),
        ForeignKey(
            "observations.observation_id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    ),
)


class LabResult(Base):
    __tablename__ = "lab_results"

    __table_args__ = (
        UniqueConstraint(
            "source",
            "source_lab_result_id",
            name="uq_lab_result_source_id",
        ),
    )

    lab_result_id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )

    source_lab_result_id: Mapped[str] = mapped_column(
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

    test_code: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )

    test_system: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    test_display: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    report_status: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    category: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    effective_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    issued_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    performer_reference: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    conclusion: Mapped[str | None] = mapped_column(
        Text,
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

    observations: Mapped[list["Observation"]] = relationship(
        "Observation",
        secondary=lab_result_observations,
        lazy="selectin",
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