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