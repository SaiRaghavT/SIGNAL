"""add deadline escalations table

Revision ID: b40a97cb74ab
Revises: 3d9090dc5883
Create Date: 2026-09-30 23:51:59.183367

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b40a97cb74ab"
down_revision: Union[str, Sequence[str], None] = "3d9090dc5883"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    op.create_table(
        "deadline_escalations",
        sa.Column(
            "escalation_id",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "case_id",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column(
            "escalation_required",
            sa.Boolean(),
            nullable=False,
        ),
        sa.Column(
            "minutes_remaining",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "deadline",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "message",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "jurisdiction",
            sa.String(length=100),
            nullable=True,
        ),
        sa.Column(
            "rule_id",
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("escalation_id"),
    )

    op.create_index(
        "ix_deadline_escalations_case_id",
        "deadline_escalations",
        ["case_id"],
        unique=False,
    )

    op.create_index(
        "ix_deadline_escalations_status",
        "deadline_escalations",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.execute(
        "DROP TABLE IF EXISTS deadline_escalations CASCADE"
    )