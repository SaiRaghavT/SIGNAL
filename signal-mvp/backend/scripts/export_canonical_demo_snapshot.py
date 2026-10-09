"""Export the checked-in synthetic canonical dataset for Alembic seeding."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
import gzip
import json
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select

from backend.app.database import SessionLocal
from backend.app.models import (
    Candidate,
    Case,
    ClinicalDocument,
    Condition,
    Encounter,
    LabResult,
    Observation,
    Patient,
)
from backend.app.models.lab_result import lab_result_observations


SOURCE_VALUES = ("synthea", "SIGNAL_DEMO")
OUTPUT_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "data"
    / "canonical_demo_snapshot.json.gz"
)


def json_value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (UUID, Decimal)):
        return str(value)
    if isinstance(value, dict):
        return {key: json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(item) for item in value]
    return value


def model_rows(db, model, *, patient_ids=None, source_filter=True):
    query = db.query(model)
    if patient_ids is not None:
        query = query.filter(model.patient_id.in_(patient_ids))
    if source_filter and hasattr(model, "source"):
        query = query.filter(model.source.in_(SOURCE_VALUES))
    return [
        {
            column.name: json_value(getattr(row, column.name))
            for column in model.__table__.columns
        }
        for row in query.all()
    ]


def main() -> None:
    db = SessionLocal()
    try:
        patient_rows = model_rows(db, Patient)
        patient_ids = [UUID(row["patient_id"]) for row in patient_rows]
        patient_id_strings = [str(patient_id) for patient_id in patient_ids]
        encounter_rows = model_rows(db, Encounter, patient_ids=patient_ids)
        condition_rows = model_rows(db, Condition, patient_ids=patient_ids)
        observation_rows = model_rows(db, Observation, patient_ids=patient_ids)
        lab_rows = model_rows(db, LabResult, patient_ids=patient_ids)
        lab_ids = [UUID(row["lab_result_id"]) for row in lab_rows]
        document_rows = model_rows(db, ClinicalDocument, patient_ids=patient_ids)
        candidate_rows = model_rows(db, Candidate, source_filter=False)
        candidate_rows = [
            row for row in candidate_rows if row["patient_id"] in patient_id_strings
        ]
        case_rows = [
            row
            for row in model_rows(db, Case, source_filter=False)
            if str((row.get("patient") or {}).get("patient_id") or "")
            in patient_id_strings
        ]

        association_rows = [
            {
                "lab_result_id": str(row.lab_result_id),
                "observation_id": str(row.observation_id),
            }
            for row in db.execute(
                select(lab_result_observations).where(
                    lab_result_observations.c.lab_result_id.in_(lab_ids)
                )
            )
        ] if lab_ids else []

        snapshot = {
            "dataset": "synthetic SIGNAL canonical patient snapshot",
            "patient_count": len(patient_rows),
            "tables": {
                "patients": patient_rows,
                "encounters": encounter_rows,
                "conditions": condition_rows,
                "observations": observation_rows,
                "lab_results": lab_rows,
                "lab_result_observations": association_rows,
                "clinical_documents": document_rows,
                "candidates": candidate_rows,
                "cases": case_rows,
            },
        }
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(OUTPUT_PATH, "wt", encoding="utf-8", compresslevel=9) as output:
            json.dump(snapshot, output, ensure_ascii=False, separators=(",", ":"))
        print(f"Exported {len(patient_rows)} patients to {OUTPUT_PATH}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
