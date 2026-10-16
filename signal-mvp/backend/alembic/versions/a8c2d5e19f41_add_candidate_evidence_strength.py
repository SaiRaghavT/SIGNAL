"""persist candidate evidence strength and explanation

Revision ID: a8c2d5e19f41
Revises: 4d6c9b9d452e
"""

from typing import Sequence, Union

revision: str = "a8c2d5e19f41"
down_revision: Union[str, Sequence[str], None] = "4d6c9b9d452e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Evidence strength is calculated from candidate.signals at request time.
    # This revision remains as a no-op to preserve the migration chain.
    pass


def downgrade() -> None:
    pass
