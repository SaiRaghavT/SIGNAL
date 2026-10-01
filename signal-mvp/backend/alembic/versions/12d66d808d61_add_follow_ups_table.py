"""add follow ups table

Revision ID: 12d66d808d61
Revises: 182c176387cd
Create Date: 2026-09-30 22:50:51.069868

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "12d66d808d61"
down_revision: Union[str, Sequence[str], None] = "182c176387cd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create follow_ups table."""

    op.create_table(
        "follow_ups",
        sa.Column(
            "followup_id",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "case_id",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "action",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column(
            "notes",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("followup_id"),
    )

    op.create_index(
        "ix_follow_ups_case_id",
        "follow_ups",
        ["case_id"],
        unique=False,
    )

    op.create_index(
        "ix_follow_ups_status",
        "follow_ups",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    """Drop follow_ups table if it exists."""

    op.execute(
        "DROP TABLE IF EXISTS follow_ups CASCADE"
    )