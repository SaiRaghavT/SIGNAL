"""seed the synthetic canonical patient dataset used by the SIGNAL POC

Revision ID: f13d9a2c6b80
Revises: 4bfa83d19c25
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
import gzip
import json
from pathlib import Path
from typing import Any
from uuid import UUID

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "f13d9a2c6b80"
down_revision = "4bfa83d19c25"
branch_labels = None
depends_on = None

SNAPSHOT_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "canonical_demo_snapshot.json.gz"
)
INSERT_ORDER = (
    "patients",
    "encounters",
    "conditions",
    "observations",
    "lab_results",
    "lab_result_observations",
    "clinical_documents",
    "candidates",
    "cases",
)
BATCH_SIZE = 1000


def _bind_value(column: sa.Column[Any], value: Any) -> Any:
    if value is None:
        return None
    column_type = column.type
    if isinstance(column_type, postgresql.UUID) and isinstance(value, str):
        return UUID(value)
    if isinstance(column_type, sa.DateTime) and isinstance(value, str):
        return datetime.fromisoformat(value)
    if isinstance(column_type, sa.Date) and isinstance(value, str):
        return date.fromisoformat(value)
    if isinstance(column_type, sa.Numeric) and isinstance(value, str):
        return Decimal(value)
    return value


def upgrade() -> None:
    with gzip.open(SNAPSHOT_PATH, "rt", encoding="utf-8") as source:
        snapshot = json.load(source)

    connection = op.get_bind()
    metadata = sa.MetaData()
    for table_name in INSERT_ORDER:
        rows = snapshot["tables"].get(table_name, [])
        if not rows:
            continue

        table = sa.Table(table_name, metadata, autoload_with=connection)
        prepared_rows = [
            {
                key: _bind_value(table.c[key], value)
                for key, value in row.items()
            }
            for row in rows
        ]
        for start in range(0, len(prepared_rows), BATCH_SIZE):
            batch = prepared_rows[start : start + BATCH_SIZE]
            statement = postgresql.insert(table).values(batch).on_conflict_do_nothing()
            connection.execute(statement)


def downgrade() -> None:
    # Preserve the shared synthetic dataset when rolling back schema revisions.
    # The seed migration inserts only and is safe to reapply on an existing DB.
    pass
