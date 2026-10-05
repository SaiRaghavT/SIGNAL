import json

from backend.app.database import SessionLocal
from backend.app.ingestion.fhir.test_fixtures import find_synthea_bundle
from backend.app.ingestion.fhir.service import ingest_fhir_bundle


def main():
    bundle_path = find_synthea_bundle()
    if bundle_path is None:
        raise FileNotFoundError(
            "Set SYNTHEA_FHIR_BUNDLE or provide data/seed/fhir fixtures."
        )

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
