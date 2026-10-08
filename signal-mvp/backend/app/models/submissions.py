from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models.base import Base


class Submission(Base):
    __tablename__ = "submissions"

    submission_id: Mapped[str] = mapped_column(
        String(255),
        primary_key=True,
        default=lambda: f"SUB-{uuid4()}",
    )

    case_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    # Historical routing choice for this specific submission.
    submission_mode: Mapped[str | None] = mapped_column(String(20), nullable=True)

    report_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        index=True,
    )

    channel: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="eCR",
        server_default="eCR",
    )

    ecr_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    destination: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    errors: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )

    warnings: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )

    ecr_payload: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    acknowledgement_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    pha_case_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
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
