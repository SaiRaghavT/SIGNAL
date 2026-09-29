from __future__ import annotations

from typing import Any, Dict


def create_normalized_patient() -> Dict[str, Any]:
    return {
        "provenance": {
            "source_system": None,
            "source_format": "FHIR",
            "fhir_version": None,
            "ingested_at": None,
        },

        "patient": {
            "id": None,
            "name": None,
            "date_of_birth": None,
            "gender": None,
        },

        "location": {
            "address": None,
            "city": None,
            "state": None,
            "postal_code": None,
            "country": None,
        },

        "conditions": [],
        "encounters": [],
        "observations": [],
        "immunizations": [],
        "diagnostic_reports": [],
        "medications": [],
        "procedures": [],
        "allergies": [],
    }