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
ID_COLUMNS = {
    "patients": "patient_id",
    "encounters": "encounter_id",
    "conditions": "condition_id",
    "observations": "observation_id",
    "lab_results": "lab_result_id",
    "clinical_documents": "document_id",
    "candidates": "candidate_id",
    "cases": "case_id",
}
NATURAL_KEY_COLUMNS = {
    "patients": ("source", "source_patient_id"),
    "encounters": ("source", "source_encounter_id"),
    "conditions": ("source", "source_condition_id"),
    "observations": ("source", "source_observation_id"),
    "lab_results": ("source", "source_lab_result_id"),
    "clinical_documents": ("source", "source_document_id"),
    "candidates": ("detection_key",),
    "cases": ("candidate_id",),
}
FOREIGN_KEY_TABLES = {
    "encounters": {"patient_id": "patients"},
    "conditions": {"patient_id": "patients", "encounter_id": "encounters"},
    "observations": {"patient_id": "patients", "encounter_id": "encounters"},
    "lab_results": {"patient_id": "patients", "encounter_id": "encounters"},
    "lab_result_observations": {
        "lab_result_id": "lab_results",
        "observation_id": "observations",
    },
    "clinical_documents": {
        "patient_id": "patients",
        "encounter_id": "encounters",
    },
    "candidates": {
        "patient_id": "patients",
        "encounter_id": "encounters",
        "case_id": "cases",
    },
    "cases": {"candidate_id": "candidates"},
}


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


def _identifier(value: Any) -> str | None:
    return str(value) if value is not None else None


def _build_id_mappings(
    connection: sa.Connection,
    metadata: sa.MetaData,
    snapshot_tables: dict[str, list[dict[str, Any]]],
) -> dict[str, dict[str, str]]:
    mappings: dict[str, dict[str, str]] = {}

    for table_name in INSERT_ORDER:
        if table_name not in ID_COLUMNS:
            continue

        table = sa.Table(table_name, metadata, autoload_with=connection)
        id_column = ID_COLUMNS[table_name]
        natural_columns = NATURAL_KEY_COLUMNS[table_name]
        selected_columns = (id_column, *natural_columns)
        existing_by_id: dict[str, str] = {}
        existing_by_natural_key: dict[tuple[str | None, ...], str] = {}
        existing_rows = connection.execute(
            sa.select(*(table.c[column] for column in selected_columns))
        ).mappings()
        for row in existing_rows:
            existing_id = str(row[id_column])
            existing_by_id[existing_id] = existing_id
            natural_key = tuple(
                _identifier(row[column]) for column in natural_columns
            )
            existing_by_natural_key[natural_key] = existing_id

        table_mappings: dict[str, str] = {}
        snapshot_natural_keys: dict[tuple[str | None, ...], str] = {}
        for row in snapshot_tables.get(table_name, []):
            source_id = str(row[id_column])
            natural_key = tuple(
                _identifier(row[column]) for column in natural_columns
            )
            if table_name == "cases":
                candidate_id = str(row["candidate_id"])
                natural_key = (
                    mappings["candidates"].get(candidate_id, candidate_id),
                )

            target_id = (
                existing_by_natural_key.get(natural_key)
                or existing_by_id.get(source_id)
                or snapshot_natural_keys.get(natural_key)
                or source_id
            )
            table_mappings[source_id] = target_id
            snapshot_natural_keys.setdefault(natural_key, target_id)

        mappings[table_name] = table_mappings

    return mappings


def upgrade() -> None:
    with gzip.open(SNAPSHOT_PATH, "rt", encoding="utf-8") as source:
        snapshot = json.load(source)

    connection = op.get_bind()
    metadata = sa.MetaData()
    id_mappings = _build_id_mappings(connection, metadata, snapshot["tables"])
    for table_name in INSERT_ORDER:
        rows = snapshot["tables"].get(table_name, [])
        if not rows:
            continue

        table = sa.Table(table_name, metadata, autoload_with=connection)
        prepared_rows = []
        for row in rows:
            remapped_row = dict(row)
            for column, referenced_table in FOREIGN_KEY_TABLES.get(
                table_name, {}
            ).items():
                value = remapped_row.get(column)
                if value is not None:
                    remapped_row[column] = id_mappings[referenced_table].get(
                        str(value), value
                    )
            prepared_rows.append(
                {
                    key: _bind_value(table.c[key], value)
                    for key, value in remapped_row.items()
                }
            )
        for start in range(0, len(prepared_rows), BATCH_SIZE):
            batch = prepared_rows[start : start + BATCH_SIZE]
            statement = postgresql.insert(table).values(batch).on_conflict_do_nothing()
            connection.execute(statement)


def downgrade() -> None:
    # Preserve the shared synthetic dataset when rolling back schema revisions.
    # The seed migration inserts only and is safe to reapply on an existing DB.
    pass
