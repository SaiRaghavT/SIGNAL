"""store initial values for repeatable SIGNAL demo workflow resets"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "d9f78a6e2c11"
down_revision: Union[str, Sequence[str], None] = "5e7a91c2d604"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "demo_case_baselines",
        sa.Column("case_id", sa.String(length=36), nullable=False),
        sa.Column("case_state", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("candidate_state", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("case_id"),
    )


def downgrade() -> None:
    op.drop_table("demo_case_baselines")
