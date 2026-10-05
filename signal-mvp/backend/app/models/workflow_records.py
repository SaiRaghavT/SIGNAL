from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models.base import Base


class CaseWorkflowRecord(Base):
    __tablename__ = "case_workflow_records"

    record_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    case_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    record_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    actor_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class Report(Base):
    __tablename__ = "reports"

    report_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    case_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    form_id: Mapped[str] = mapped_column(String(255), nullable=False)
    form_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    render_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    report_type: Mapped[str] = mapped_column(String(100), nullable=False, default="TEXAS_MEASLES")
    disease: Mapped[str | None] = mapped_column(String(100), nullable=True)
    jurisdiction: Mapped[str | None] = mapped_column(String(100), nullable=True)
    validation: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    attestation: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="GENERATED", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Acknowledgement(Base):
    __tablename__ = "acknowledgements"

    acknowledgement_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    submission_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    pha_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    response: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    errors: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class SubmissionAttempt(Base):
    __tablename__ = "submission_attempts"

    attempt_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    original_submission_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    new_submission_id: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    attempt_number: Mapped[int] = mapped_column(nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
