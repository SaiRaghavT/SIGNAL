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


class ClinicalDocument(Base):
    __tablename__ = "clinical_documents"

    __table_args__ = (
        UniqueConstraint(
            "source",
            "source_document_id",
            name="uq_clinical_document_source_id",
        ),
    )

    document_id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )

    source_document_id: Mapped[str] = mapped_column(
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

    document_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    document_status: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    title: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    document_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    author_reference: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    content_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    content_location: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    extracted_text: Mapped[str | None] = mapped_column(
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