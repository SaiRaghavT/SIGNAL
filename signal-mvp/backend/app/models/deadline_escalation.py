from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models.base import Base


class DeadlineEscalation(Base):
    __tablename__ = "deadline_escalations"

    escalation_id: Mapped[str] = mapped_column(
        String(255),
        primary_key=True,
    )

    case_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    escalation_required: Mapped[bool] = mapped_column(
        nullable=False,
    )

    minutes_remaining: Mapped[int | None] = mapped_column(
        nullable=True,
    )

    deadline: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    jurisdiction: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    rule_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )