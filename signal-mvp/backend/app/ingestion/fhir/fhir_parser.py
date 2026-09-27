from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


class FHIRParser:
    """
    Parses a FHIR JSON file or FHIR Bundle
    and groups resources by resourceType.
    """

    def __init__(self, file_path: str | Path):
        self.file_path = Path(file_path)

    def load(self) -> Dict[str, Any]:
        """Load the FHIR JSON file."""

        if not self.file_path.exists():
            raise FileNotFoundError(
                f"FHIR file not found: {self.file_path}"
            )

        with self.file_path.open(
            "r",
            encoding="utf-8"
        ) as file:
            data = json.load(file)

        if not isinstance(data, dict):
            raise ValueError(
                "FHIR JSON must contain a JSON object."
            )

        return data

    def parse(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Parse a FHIR Bundle and group resources
        by their resourceType.
        """

        data = self.load()

        resources: Dict[str, List[Dict[str, Any]]] = {}

        # Handle FHIR Bundle
        if data.get("resourceType") == "Bundle":

            entries = data.get("entry", [])

            if not isinstance(entries, list):
                raise ValueError(
                    "FHIR Bundle 'entry' must be a list."
                )

            for entry in entries:

                if not isinstance(entry, dict):
                    continue

                resource = entry.get("resource")

                if not isinstance(resource, dict):
                    continue

                resource_type = resource.get(
                    "resourceType"
                )

                if not resource_type:
                    continue

                resources.setdefault(
                    resource_type,
                    []
                ).append(resource)

        # Handle a single FHIR resource
        else:

            resource_type = data.get(
                "resourceType"
            )

            if not resource_type:
                raise ValueError(
                    "FHIR resourceType is missing."
                )

            resources[resource_type] = [data]

        return resources

    def get_resources(
        self,
        resource_type: str
    ) -> List[Dict[str, Any]]:

        resources = self.parse()

        return resources.get(
            resource_type,
            []
        )

    def get_patient(
        self
    ) -> Dict[str, Any] | None:

        patients = self.get_resources(
            "Patient"
        )

        return patients[0] if patients else None

    def get_conditions(
        self
    ) -> List[Dict[str, Any]]:

        return self.get_resources(
            "Condition"
        )

    def get_encounters(
        self
    ) -> List[Dict[str, Any]]:

        return self.get_resources(
            "Encounter"
        )

    def get_observations(
        self
    ) -> List[Dict[str, Any]]:

        return self.get_resources(
            "Observation"
        )

    def get_immunizations(
        self
    ) -> List[Dict[str, Any]]:

        return self.get_resources(
            "Immunization"
        )

    def get_diagnostic_reports(
        self
    ) -> List[Dict[str, Any]]:

        return self.get_resources(
            "DiagnosticReport"
        )

    def get_medications(
        self
    ) -> List[Dict[str, Any]]:

        return self.get_resources(
            "MedicationRequest"
        )

    def get_procedures(
        self
    ) -> List[Dict[str, Any]]:

        return self.get_resources(
            "Procedure"
        )

    def get_allergies(
        self
    ) -> List[Dict[str, Any]]:

        return self.get_resources(
            "AllergyIntolerance"
        )

    def get_organizations(
        self
    ) -> List[Dict[str, Any]]:

        return self.get_resources(
            "Organization"
        )

    def get_practitioners(
        self
    ) -> List[Dict[str, Any]]:

        return self.get_resources(
            "Practitioner"
        )

    def summary(
        self
    ) -> Dict[str, int]:
        """
        Return the number of resources
        grouped by resourceType.
        """

        resources = self.parse()

        return {
            resource_type: len(items)
            for resource_type, items
            in resources.items()
        }


def parse_fhir_file(
    file_path: str | Path
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Convenience function for parsing
    a FHIR JSON file.
    """

    parser = FHIRParser(file_path)

    return parser.parse()