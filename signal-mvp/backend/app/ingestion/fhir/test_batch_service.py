import json
from pathlib import Path

from backend.app.database import SessionLocal
from backend.app.ingestion.fhir.batch_service import ingest_fhir_bundles


SYNTHEA_BUNDLE = Path(
    r"C:\Users\i-nandhini.annikalla\OneDrive - Feuji Software Solutions Pvt Ltd\Desktop\Signal\SIGNAL\synthea\output\fhir\Agustin437_Lindgren255_1f8b4384-cb39-6fab-3ca5-adb869c3ab03.json"
)


def test_multiple_fhir_bundles():

    assert SYNTHEA_BUNDLE.exists(), (
        f"Synthea Bundle not found: {SYNTHEA_BUNDLE}"
    )

    with SYNTHEA_BUNDLE.open(
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

        assert result["total_counts"]["patients"] == 2
        assert result["total_counts"]["encounters"] == 36
        assert result["total_counts"]["conditions"] == 50
        assert result["total_counts"]["observations"] == 232
        assert result["total_counts"]["lab_results"] == 74
        assert result["total_counts"]["clinical_documents"] == 36

    finally:
        db.close()