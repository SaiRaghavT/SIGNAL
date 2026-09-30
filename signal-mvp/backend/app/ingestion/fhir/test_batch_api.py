import json
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.main import app


SYNTHEA_BUNDLE = Path(
    r"C:\Users\i-nandhini.annikalla\OneDrive - Feuji Software Solutions Pvt Ltd\Desktop\Signal\SIGNAL\synthea\output\fhir\Agustin437_Lindgren255_1f8b4384-cb39-6fab-3ca5-adb869c3ab03.json"
)


client = TestClient(app)


def test_fhir_batch_api():

    assert SYNTHEA_BUNDLE.exists(), (
        f"Synthea Bundle not found: {SYNTHEA_BUNDLE}"
    )

    with SYNTHEA_BUNDLE.open(
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