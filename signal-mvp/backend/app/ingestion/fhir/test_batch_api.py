import json
import pytest

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.ingestion.fhir.test_fixtures import find_synthea_bundle


client = TestClient(app)


def test_fhir_batch_api():
    bundle_path = find_synthea_bundle()
    if bundle_path is None:
        pytest.skip("Set SYNTHEA_FHIR_BUNDLE or provide data/seed/fhir fixtures.")

    with bundle_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        payload = json.load(file)

    response = client.post(
        "/api/ingestion/fhir/batch?source=synthea",
        json={
            "bundles": [
                payload,
                payload,
            ]
        },
    )

    assert response.status_code == 200

    result = response.json()

    assert result["status"] == "success"
    assert result["source"] == "synthea"
    assert result["total_bundles"] == 2
    assert result["successful_bundles"] == 2
    assert result["failed_bundles"] == 0