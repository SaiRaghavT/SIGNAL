"""add audit events table

Revision ID: 3d9090dc5883
Revises: 12d66d808d61
Create Date: 2026-09-30 23:15:30.019325

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "3d9090dc5883"
down_revision: Union[str, Sequence[str], None] = "12d66d808d61"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create audit_events table."""

    op.create_table(
        "audit_events",
        sa.Column(
            "audit_id",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "entity_type",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            "entity_id",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "event_type",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            "actor_type",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            "actor_id",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "source_agent",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "previous_value",
            postgresql.JSONB(),
            nullable=True,
        ),
        sa.Column(
            "new_value",
            postgresql.JSONB(),
            nullable=True,
        ),
        sa.Column(
            "metadata",
            postgresql.JSONB(),
            nullable=False,
        ),
        sa.Column(
            "event_timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("audit_id"),
    )

    op.create_index(
        "ix_audit_events_entity_type",
        "audit_events",
        ["entity_type"],
        unique=False,
    )

    op.create_index(
        "ix_audit_events_entity_id",
        "audit_events",
        ["entity_id"],
        unique=False,
    )

    op.create_index(
        "ix_audit_events_event_type",
        "audit_events",
        ["event_type"],
        unique=False,
    )


def downgrade() -> None:
    """Drop audit_events table if it exists."""

    op.execute(
        "DROP TABLE IF EXISTS audit_events CASCADE"
    )