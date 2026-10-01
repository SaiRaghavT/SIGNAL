import os
import requests


class CanonicalClient:
    """
    Client used by Member 2 to retrieve canonical
    patient context from Member 1.
    """

    def __init__(self):
        self.base_url = os.getenv(
            "CANONICAL_API_URL",
            "http://localhost:8000"
        )

    def get_patient_context(self, patient_id: str) -> dict:
        """
        Retrieve complete canonical context for a patient.
        """

        url = (
            f"{self.base_url}"
            f"/api/canonical/patients/{patient_id}"
        )

        response = requests.get(
            url,
            timeout=30,
        )

        response.raise_for_status()

        return response.json()
