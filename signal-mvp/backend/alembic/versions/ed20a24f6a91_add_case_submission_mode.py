"""add shared submission mode to cases

Revision ID: ed20a24f6a91
Revises: ab61f2d490ad
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "ed20a24f6a91"
down_revision: Union[str, Sequence[str], None] = "ab61f2d490ad"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("cases", sa.Column("submission_mode", sa.String(length=20), nullable=True))
    op.create_index("ix_cases_submission_mode", "cases", ["submission_mode"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_cases_submission_mode", table_name="cases")
    op.drop_column("cases", "submission_mode")
