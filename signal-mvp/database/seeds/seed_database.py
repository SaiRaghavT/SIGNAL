import json
from pathlib import Path
from typing import Any

from backend.app.database import SessionLocal
from backend.app.ingestion.fhir.batch_service import ingest_fhir_bundles


def load_fhir_bundles(seed_dir: Path) -> list[dict[str, Any]]:
    bundles = []

    for file_path in sorted(seed_dir.glob("*.json")):
        with file_path.open("r", encoding="utf-8") as file:
            bundles.append(json.load(file))

    if not bundles:
        raise RuntimeError(
            f"No FHIR JSON files found in: {seed_dir}"
        )

    return bundles


def seed_database() -> None:
    # signal-mvp/
    # └── database/
    #     └── seeds/
    #         └── seed_database.py
    project_root = Path(__file__).resolve().parents[2]

    seed_dir = project_root / "data" / "seed" / "fhir"

    print(f"Loading FHIR seed data from: {seed_dir}")

    bundles = load_fhir_bundles(seed_dir)

    print(f"Found {len(bundles)} FHIR bundles")

    db = SessionLocal()

    try:
        result = ingest_fhir_bundles(
            db=db,
            payloads=bundles,
            source="synthea",
        )

        print("\nSeed result:")
        print(f"Status: {result['status']}")
        print(f"Total bundles: {result['total_bundles']}")
        print(f"Successful: {result['successful_bundles']}")
        print(f"Failed: {result['failed_bundles']}")
        print(
            f"Canonical records: "
            f"{result['total_canonical_records']}"
        )

        if result["failed_bundles"] > 0:
            raise RuntimeError(
                "Database seeding completed with failures."
            )

    finally:
        db.close()


if __name__ == "__main__":
    seed_database()