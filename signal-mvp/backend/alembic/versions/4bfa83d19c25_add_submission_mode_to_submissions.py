"""add submission mode snapshot to submissions

Revision ID: 4bfa83d19c25
Revises: ed20a24f6a91
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "4bfa83d19c25"
down_revision: Union[str, Sequence[str], None] = "ed20a24f6a91"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("submissions", sa.Column("submission_mode", sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column("submissions", "submission_mode")
