"""persist smart and human-completed reporting fields

Revision ID: c91f4a87d2e1
Revises: b40a97cb74ab
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "c91f4a87d2e1"
down_revision: Union[str, Sequence[str], None] = "b40a97cb74ab"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "cases",
        sa.Column(
            "report_fields",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.alter_column("cases", "report_fields", server_default=None)


def downgrade() -> None:
    op.drop_column("cases", "report_fields")
