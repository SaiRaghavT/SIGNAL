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

SOURCE_KEY_COLUMNS = {
    "patients": ("patient_id", "source_patient_id"),
    "encounters": ("encounter_id", "source_encounter_id"),
    "conditions": ("condition_id", "source_condition_id"),
    "observations": ("observation_id", "source_observation_id"),
    "lab_results": ("lab_result_id", "source_lab_result_id"),
    "clinical_documents": ("document_id", "source_document_id"),
}


def _as_key(value: Any) -> str | None:
    return None if value is None else str(value)


def _natural_id_map(
    connection: sa.Connection,
    table: sa.Table,
    primary_key: str,
    source_key: str,
    rows: list[dict[str, Any]],
) -> dict[str, str]:
    """Map snapshot ids onto rows already present by their stable source identity."""
    stored = connection.execute(
        sa.select(table.c[primary_key], table.c.source, table.c[source_key])
    ).all()
    stored_by_identity = {
        (_as_key(source), _as_key(external_id)): _as_key(row_id)
        for row_id, source, external_id in stored
        if external_id is not None
    }
    return {
        _as_key(row[primary_key]): stored_by_identity.get(
            (_as_key(row.get("source")), _as_key(row.get(source_key))),
            _as_key(row[primary_key]),
        )
        for row in rows
    }


def _remap_columns(row: dict[str, Any], maps: dict[str, dict[str, str]]) -> None:
    for column, id_map in maps.items():
        value = row.get(column)
        if value is not None:
            row[column] = id_map.get(str(value), value)


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
    id_maps: dict[str, dict[str, str]] = {}
    snapshot_rows = snapshot["tables"]
    for table_name in INSERT_ORDER:
        rows = snapshot_rows.get(table_name, [])
        if not rows:
            continue

        table = sa.Table(table_name, metadata, autoload_with=connection)
        prepared_rows = []
        for source_row in rows:
            row = {
                key: _bind_value(table.c[key], value)
                for key, value in source_row.items()
            }
            if table_name == "encounters":
                _remap_columns(row, {"patient_id": id_maps.get("patients", {})})
            elif table_name in {"conditions", "observations", "lab_results", "clinical_documents"}:
                _remap_columns(row, {
                    "patient_id": id_maps.get("patients", {}),
                    "encounter_id": id_maps.get("encounters", {}),
                })
            elif table_name == "lab_result_observations":
                _remap_columns(row, {
                    "lab_result_id": id_maps.get("lab_results", {}),
                    "observation_id": id_maps.get("observations", {}),
                })
            elif table_name == "candidates":
                _remap_columns(row, {
                    "patient_id": id_maps.get("patients", {}),
                    "encounter_id": id_maps.get("encounters", {}),
                })
            elif table_name == "cases":
                _remap_columns(row, {"candidate_id": id_maps.get("candidates", {})})
                patient = row.get("patient")
                if isinstance(patient, dict) and patient.get("patient_id") is not None:
                    patient = dict(patient)
                    patient_map = id_maps.get("patients", {})
                    patient["patient_id"] = patient_map.get(
                        str(patient["patient_id"]), patient["patient_id"]
                    )
                    row["patient"] = patient
            prepared_rows.append(row)

        for start in range(0, len(prepared_rows), BATCH_SIZE):
            batch = prepared_rows[start : start + BATCH_SIZE]
            statement = postgresql.insert(table).values(batch).on_conflict_do_nothing()
            connection.execute(statement)

        if table_name in SOURCE_KEY_COLUMNS:
            primary_key, source_key = SOURCE_KEY_COLUMNS[table_name]
            id_maps[table_name] = _natural_id_map(
                connection, table, primary_key, source_key, rows
            )
        elif table_name == "candidates":
            existing = connection.execute(
                sa.select(table.c.candidate_id, table.c.detection_key)
            ).all()
            by_detection_key = {
                _as_key(detection_key): _as_key(candidate_id)
                for candidate_id, detection_key in existing
                if detection_key is not None
            }
            id_maps[table_name] = {
                str(row["candidate_id"]): by_detection_key.get(
                    _as_key(row.get("detection_key")), str(row["candidate_id"])
                )
                for row in rows
            }
        elif table_name == "cases":
            existing = connection.execute(
                sa.select(table.c.case_id, table.c.candidate_id)
            ).all()
            by_candidate = {
                _as_key(candidate_id): _as_key(case_id)
                for case_id, candidate_id in existing
                if candidate_id is not None
            }
            id_maps[table_name] = {
                str(row["case_id"]): by_candidate.get(
                    _as_key(id_maps.get("candidates", {}).get(
                        str(row.get("candidate_id")), row.get("candidate_id")
                    )),
                    str(row["case_id"]),
                )
                for row in rows
            }

    # Candidate rows carry a denormalized case link without a database FK.
    # Repair it when a snapshot case was mapped to an existing canonical row.
    candidates = sa.Table("candidates", metadata, autoload_with=connection)
    for row in snapshot_rows.get("candidates", []):
        candidate_id = id_maps.get("candidates", {}).get(str(row["candidate_id"]))
        case_id = id_maps.get("cases", {}).get(str(row.get("case_id")))
        if candidate_id and case_id:
            connection.execute(
                candidates.update()
                .where(candidates.c.candidate_id == candidate_id)
                .values(case_id=case_id)
            )


def downgrade() -> None:
    # Preserve the shared synthetic dataset when rolling back schema revisions.
    # The seed migration inserts only and is safe to reapply on an existing DB.
    pass
