import json
from pathlib import Path

from backend.app.ingestion.fhir.parser import parse_fhir_bundle
from backend.app.ingestion.fhir.validator import validate_fhir_bundle
from backend.app.quality.fhir_quality import validate_fhir_data_quality


def test_fhir_data_quality():
    """
    Validate the quality of a real Synthea FHIR Bundle.
    """

    # ---------------------------------------------------------
    # Synthea test Bundle
    # ---------------------------------------------------------

    bundle_path = Path(
        r"C:\Users\i-nandhini.annikalla\OneDrive - Feuji Software Solutions Pvt Ltd\Desktop\Signal\SIGNAL\synthea\output\fhir\Agustin437_Lindgren255_1f8b4384-cb39-6fab-3ca5-adb869c3ab03.json"
    )

    assert bundle_path.exists(), (
        f"Synthea FHIR Bundle not found: {bundle_path}"
    )

    # ---------------------------------------------------------
    # Load FHIR Bundle
    # ---------------------------------------------------------

    with bundle_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        payload = json.load(file)

    # ---------------------------------------------------------
    # Structural validation
    # ---------------------------------------------------------

    validate_fhir_bundle(payload)

    # ---------------------------------------------------------
    # Parse FHIR resources
    # ---------------------------------------------------------

    resources = parse_fhir_bundle(payload)

    # ---------------------------------------------------------
    # Data-quality validation
    # ---------------------------------------------------------

    quality_result = validate_fhir_data_quality(resources)

    # ---------------------------------------------------------
    # Display result
    # ---------------------------------------------------------

    print("\n")
    print("SIGNAL FHIR Data Quality Verification")
    print("-------------------------------------")
    print(f"Status:   {quality_result['status']}")
    print(f"Errors:   {quality_result['error_count']}")
    print(f"Warnings: {quality_result['warning_count']}")
    print(f"Issues:   {quality_result['issue_count']}")

    if quality_result["issues"]:
        print("\nIssues:")

        for issue in quality_result["issues"]:
            print(
                f"- [{issue['severity']}] "
                f"{issue['resource_type']} "
                f"{issue['resource_id']} "
                f"{issue['field']}: "
                f"{issue['message']}"
            )

    # ---------------------------------------------------------
    # Test assertion
    # ---------------------------------------------------------

    assert quality_result["status"] == "passed"
    assert quality_result["error_count"] == 0