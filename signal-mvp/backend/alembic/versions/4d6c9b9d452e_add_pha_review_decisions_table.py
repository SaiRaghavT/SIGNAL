
"""add pha review decisions table

Revision ID: 4d6c9b9d452e
Revises: f13d9a2c6b80
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "4d6c9b9d452e"
down_revision: Union[str, Sequence[str], None] = "f13d9a2c6b80"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pha_review_decisions",
        sa.Column(
            "decision_id",
            sa.String(length=36),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "submission_id",
            sa.String(length=255),
            sa.ForeignKey("submissions.submission_id"),
            nullable=False,
        ),
        sa.Column(
            "decision",
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column(
            "reviewer",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "reason",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "requested_information",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_index(
        "ix_pha_review_decisions_submission_id",
        "pha_review_decisions",
        ["submission_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_pha_review_decisions_submission_id",
        table_name="pha_review_decisions",
    )
    op.drop_table("pha_review_decisions")
