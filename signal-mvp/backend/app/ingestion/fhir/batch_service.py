from typing import Any

from sqlalchemy.orm import Session

from backend.app.ingestion.fhir.service import ingest_fhir_bundle


def ingest_fhir_bundles(
    db: Session,
    payloads: list[dict[str, Any]],
    source: str = "synthea",
) -> dict[str, Any]:
    """
    Ingest multiple FHIR Bundles using the existing
    single-Bundle ingestion service.

    Each Bundle is processed independently.

    If one Bundle fails:
        - that Bundle is rolled back
        - previously successful Bundles remain committed
        - processing continues with the remaining Bundles
    """

    if not isinstance(payloads, list):
        raise ValueError(
            "FHIR batch payload must be a list of Bundles."
        )

    if not payloads:
        raise ValueError(
            "FHIR batch must contain at least one Bundle."
        )

    successful = 0
    failed = 0

    total_counts = {
        "patients": 0,
        "encounters": 0,
        "conditions": 0,
        "observations": 0,
        "lab_results": 0,
        "clinical_documents": 0,
    }

    results: list[dict[str, Any]] = []

    for index, payload in enumerate(payloads):

        try:
            result = ingest_fhir_bundle(
                db=db,
                payload=payload,
                source=source,
            )

            successful += 1

            counts = result.get("counts", {})

            for resource_type in total_counts:
                total_counts[resource_type] += counts.get(
                    resource_type,
                    0,
                )

            results.append(
                {
                    "index": index,
                    "status": "success",
                    "result": result,
                }
            )

        except Exception as exc:

            failed += 1

            results.append(
                {
                    "index": index,
                    "status": "failed",
                    "error": str(exc),
                }
            )

    return {
        "status": (
            "success"
            if failed == 0
            else "partial_success"
            if successful > 0
            else "failed"
        ),
        "source": source,
        "total_bundles": len(payloads),
        "successful_bundles": successful,
        "failed_bundles": failed,
        "total_counts": total_counts,
        "total_canonical_records": sum(
            total_counts.values()
        ),
        "results": results,
    }