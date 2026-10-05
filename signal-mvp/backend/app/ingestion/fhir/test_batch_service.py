import json
import pytest

from backend.app.database import SessionLocal
from backend.app.ingestion.fhir.batch_service import ingest_fhir_bundles
from backend.app.ingestion.fhir.test_fixtures import find_synthea_bundle


def test_multiple_fhir_bundles():
    bundle_path = find_synthea_bundle()
    if bundle_path is None:
        pytest.skip("Set SYNTHEA_FHIR_BUNDLE or provide data/seed/fhir fixtures.")

    with bundle_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        payload = json.load(file)

    db = SessionLocal()

    try:
        result = ingest_fhir_bundles(
            db=db,
            payloads=[
                payload,
                payload,
            ],
            source="synthea",
        )

        assert result["status"] == "success"
        assert result["total_bundles"] == 2
        assert result["successful_bundles"] == 2
        assert result["failed_bundles"] == 0

        expected_counts = {
            resource_type: sum(
                item["result"]["counts"].get(resource_type, 0)
                for item in result["results"]
                if item["status"] == "success"
            )
            for resource_type in result["total_counts"]
        }
        assert result["total_counts"] == expected_counts

    finally:
        db.close()