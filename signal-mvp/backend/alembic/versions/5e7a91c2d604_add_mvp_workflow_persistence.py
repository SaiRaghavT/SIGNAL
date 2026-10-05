"""add persistent MVP workflow records

Revision ID: 5e7a91c2d604
Revises: c91f4a87d2e1
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "5e7a91c2d604"
down_revision: Union[str, Sequence[str], None] = "c91f4a87d2e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "candidates",
        sa.Column("candidate_id", sa.String(36), nullable=False),
        sa.Column("detection_key", sa.String(64), nullable=False),
        sa.Column("patient_id", sa.String(36), nullable=False),
        sa.Column("encounter_id", sa.String(255), nullable=True),
        sa.Column("disease_id", sa.String(100), nullable=False),
        sa.Column("jurisdiction", sa.String(100), nullable=True),
        sa.Column("case_id", sa.String(36), nullable=True),
        sa.Column("detection_source", sa.String(100), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("evidence", postgresql.JSONB(), nullable=False),
        sa.Column("signals", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("severity", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("candidate_id"),
        sa.UniqueConstraint("detection_key", name="uq_candidates_detection_key"),
    )
    op.create_index("ix_candidates_patient_id", "candidates", ["patient_id"])
    op.create_index("ix_candidates_encounter_id", "candidates", ["encounter_id"])
    op.create_index("ix_candidates_disease_id", "candidates", ["disease_id"])
    op.create_index("ix_candidates_case_id", "candidates", ["case_id"])
    op.create_index("ix_candidates_status", "candidates", ["status"])
    op.create_index("ix_candidates_severity", "candidates", ["severity"])
    op.create_index("ix_candidates_deadline", "candidates", ["deadline"])

    op.add_column("cases", sa.Column("deadline", sa.DateTime(timezone=True), nullable=True))
    op.add_column("cases", sa.Column("severity", sa.String(20), nullable=True))
    op.create_index("ix_cases_deadline", "cases", ["deadline"])
    op.create_index("ix_cases_severity", "cases", ["severity"])

    op.add_column("submissions", sa.Column("report_id", sa.String(36), nullable=True))
    op.add_column("submissions", sa.Column("channel", sa.String(100), server_default="eCR", nullable=False))
    op.add_column("submissions", sa.Column("acknowledgement_id", sa.String(255), nullable=True))
    op.add_column("submissions", sa.Column("pha_case_id", sa.String(255), nullable=True))
    op.add_column("submissions", sa.Column("ecr_payload", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")))
    op.alter_column("submissions", "ecr_payload", server_default=None)
    op.create_index("ix_submissions_report_id", "submissions", ["report_id"])

    op.add_column("follow_ups", sa.Column("submission_id", sa.String(255), nullable=True))
    op.add_column("follow_ups", sa.Column("patient_id", sa.String(36), nullable=True))
    op.add_column("follow_ups", sa.Column("disease", sa.String(100), nullable=True))
    op.add_column("follow_ups", sa.Column("next_action", sa.Text(), nullable=True))
    op.add_column("follow_ups", sa.Column("due_date", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_follow_ups_submission_id", "follow_ups", ["submission_id"])
    op.create_index("ix_follow_ups_patient_id", "follow_ups", ["patient_id"])

    op.create_table(
        "case_workflow_records",
        sa.Column("record_id", sa.String(36), nullable=False),
        sa.Column("case_id", sa.String(36), nullable=False),
        sa.Column("record_type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("actor_id", sa.String(255), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("record_id"),
    )
    op.create_index("ix_case_workflow_records_case_id", "case_workflow_records", ["case_id"])
    op.create_index("ix_case_workflow_records_record_type", "case_workflow_records", ["record_type"])
    op.create_index("ix_case_workflow_records_status", "case_workflow_records", ["status"])

    op.create_table(
        "reports",
        sa.Column("report_id", sa.String(36), nullable=False),
        sa.Column("case_id", sa.String(36), nullable=False),
        sa.Column("form_id", sa.String(255), nullable=False),
        sa.Column("form_version", sa.String(100), nullable=True),
        sa.Column("render_id", sa.String(32), nullable=True),
        sa.Column("report_type", sa.String(100), nullable=False),
        sa.Column("disease", sa.String(100), nullable=True),
        sa.Column("jurisdiction", sa.String(100), nullable=True),
        sa.Column("validation", postgresql.JSONB(), nullable=False),
        sa.Column("attestation", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("report_id"),
    )
    op.create_index("ix_reports_case_id", "reports", ["case_id"])
    op.create_index("ix_reports_status", "reports", ["status"])

    op.create_table(
        "acknowledgements",
        sa.Column("acknowledgement_id", sa.String(255), nullable=False),
        sa.Column("submission_id", sa.String(255), nullable=False),
        sa.Column("pha_id", sa.String(255), nullable=True),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("response", postgresql.JSONB(), nullable=False),
        sa.Column("errors", postgresql.JSONB(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("acknowledgement_id"),
    )
    op.create_index("ix_acknowledgements_submission_id", "acknowledgements", ["submission_id"])

    op.create_table(
        "submission_attempts",
        sa.Column("attempt_id", sa.String(36), nullable=False),
        sa.Column("original_submission_id", sa.String(255), nullable=False),
        sa.Column("new_submission_id", sa.String(255), nullable=True),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("attempt_id"),
        sa.UniqueConstraint("new_submission_id"),
    )
    op.create_index("ix_submission_attempts_original_submission_id", "submission_attempts", ["original_submission_id"])


def downgrade() -> None:
    op.drop_index("ix_submission_attempts_original_submission_id", table_name="submission_attempts")
    op.drop_table("submission_attempts")
    op.drop_index("ix_acknowledgements_submission_id", table_name="acknowledgements")
    op.drop_table("acknowledgements")
    op.drop_index("ix_reports_status", table_name="reports")
    op.drop_index("ix_reports_case_id", table_name="reports")
    op.drop_table("reports")
    op.drop_index("ix_case_workflow_records_status", table_name="case_workflow_records")
    op.drop_index("ix_case_workflow_records_record_type", table_name="case_workflow_records")
    op.drop_index("ix_case_workflow_records_case_id", table_name="case_workflow_records")
    op.drop_table("case_workflow_records")
    op.drop_index("ix_follow_ups_patient_id", table_name="follow_ups")
    op.drop_index("ix_follow_ups_submission_id", table_name="follow_ups")
    op.drop_column("follow_ups", "due_date")
    op.drop_column("follow_ups", "next_action")
    op.drop_column("follow_ups", "disease")
    op.drop_column("follow_ups", "patient_id")
    op.drop_column("follow_ups", "submission_id")
    op.drop_index("ix_submissions_report_id", table_name="submissions")
    op.drop_column("submissions", "pha_case_id")
    op.drop_column("submissions", "acknowledgement_id")
    op.drop_column("submissions", "ecr_payload")
    op.drop_column("submissions", "channel")
    op.drop_column("submissions", "report_id")
    op.drop_index("ix_cases_severity", table_name="cases")
    op.drop_index("ix_cases_deadline", table_name="cases")
    op.drop_column("cases", "severity")
    op.drop_column("cases", "deadline")
    op.drop_index("ix_candidates_status", table_name="candidates")
    op.drop_index("ix_candidates_severity", table_name="candidates")
    op.drop_index("ix_candidates_deadline", table_name="candidates")
    op.drop_index("ix_candidates_disease_id", table_name="candidates")
    op.drop_index("ix_candidates_case_id", table_name="candidates")
    op.drop_index("ix_candidates_encounter_id", table_name="candidates")
    op.drop_index("ix_candidates_patient_id", table_name="candidates")
    op.drop_table("candidates")
