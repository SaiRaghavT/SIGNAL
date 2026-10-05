import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_FHIR_DIR = PROJECT_ROOT / "data" / "seed" / "fhir"


def find_synthea_bundle() -> Path | None:
    configured_bundle = os.environ.get("SYNTHEA_FHIR_BUNDLE")
    if configured_bundle:
        bundle_path = Path(configured_bundle).expanduser()
        return bundle_path if bundle_path.is_file() else None

    configured_directory = os.environ.get("SYNTHEA_FHIR_DIR")
    fhir_directory = (
        Path(configured_directory).expanduser()
        if configured_directory
        else DEFAULT_FHIR_DIR
    )
    return next(iter(sorted(fhir_directory.glob("*.json"))), None)