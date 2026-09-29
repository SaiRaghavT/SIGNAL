from backend.app.canonical.observation_mapper import (
    map_fhir_observation,
)
from backend.app.canonical.persistence import (
    save_observation,
)
from backend.app.database import SessionLocal
from backend.app.models.encounter import Encounter
from backend.app.models.patient import Patient


def main():
    db = SessionLocal()

    try:
        patient = (
            db.query(Patient)
            .filter(
                Patient.source == "synthea",
                Patient.source_patient_id == "synthea-test-001",
            )
            .first()
        )

        if patient is None:
            raise RuntimeError(
                "Test patient 'synthea-test-001' was not found."
            )

        encounter = (
            db.query(Encounter)
            .filter(
                Encounter.source == "synthea",
                Encounter.source_encounter_id
                == "encounter-test-001",
            )
            .first()
        )

        if encounter is None:
            raise RuntimeError(
                "Test encounter 'encounter-test-001' was not found."
            )

        resource = {
            "resourceType": "Observation",
            "id": "observation-test-001",
            "status": "final",
            "code": {
                "coding": [
                    {
                        "system": "http://loinc.org",
                        "code": "8302-2",
                        "display": "Body height",
                    }
                ]
            },
            "valueQuantity": {
                "value": 173.1,
                "unit": "cm",
                "system": "http://unitsofmeasure.org",
                "code": "cm",
            },
            "effectiveDateTime": (
                "2025-01-10T10:00:00Z"
            ),
        }

        observation = map_fhir_observation(
            resource=resource,
            patient_id=patient.patient_id,
            encounter_id=encounter.encounter_id,
            source="synthea",
        )

        saved_observation = save_observation(
            db=db,
            observation=observation,
        )

        print("Observation persisted successfully")
        print(
            "SIGNAL observation_id:",
            saved_observation.observation_id,
        )
        print(
            "Source observation ID:",
            saved_observation.source_observation_id,
        )
        print(
            "Linked patient_id:",
            saved_observation.patient_id,
        )
        print(
            "Linked encounter_id:",
            saved_observation.encounter_id,
        )
        print(
            "Observation value:",
            saved_observation.value_numeric,
            saved_observation.unit,
        )

    finally:
        db.close()


if __name__ == "__main__":
    main()