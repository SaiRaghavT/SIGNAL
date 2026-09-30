import json
from pathlib import Path

from backend.app.database import SessionLocal
from backend.app.ingestion.fhir.service import ingest_fhir_bundle


FHIR_DIR = Path(
    r"C:\Users\i-nandhini.annikalla"
    r"\OneDrive - Feuji Software Solutions Pvt Ltd"
    r"\Desktop\Signal\SIGNAL\synthea\output\fhir"
)


def find_first_fhir_bundle() -> Path:
    files = sorted(FHIR_DIR.glob("*.json"))

    if not files:
        raise FileNotFoundError(
            f"No FHIR JSON files found in: {FHIR_DIR}"
        )

    return files[0]


def main():
    bundle_path = find_first_fhir_bundle()

    print(f"Processing: {bundle_path.name}")

    with bundle_path.open("r", encoding="utf-8") as file:
        bundle = json.load(file)

    db = SessionLocal()

    try:
        result = ingest_fhir_bundle(
            db=db,
            payload=bundle,
            source="synthea",
        )

        print("\nFHIR Bundle ingestion successful")
        print("--------------------------------")
        print(f"File: {bundle_path.name}")
        print(f"Status: {result['status']}")
        print(f"Source: {result['source']}")
        print(f"Resource type: {result['resource_type']}")
        print("\nCanonical records:")

        for resource_type, count in result["counts"].items():
            print(f"  {resource_type}: {count}")

        print(
            f"\nTotal canonical records: "
            f"{result['total_canonical_records']}"
        )

    except Exception:
        print("\nFHIR Bundle ingestion FAILED")
        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()
