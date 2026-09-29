from backend.app.canonical.condition_mapper import (
    map_fhir_condition,
)
from backend.app.canonical.persistence import (
    save_condition,
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
            "resourceType": "Condition",
            "id": "condition-test-001",
            "clinicalStatus": {
                "coding": [
                    {
                        "system": (
                            "http://terminology.hl7.org/"
                            "CodeSystem/condition-clinical"
                        ),
                        "code": "active",
                        "display": "Active",
                    }
                ]
            },
            "verificationStatus": {
                "coding": [
                    {
                        "system": (
                            "http://terminology.hl7.org/"
                            "CodeSystem/condition-ver-status"
                        ),
                        "code": "confirmed",
                        "display": "Confirmed",
                    }
                ]
            },
            "code": {
                "coding": [
                    {
                        "system": "http://snomed.info/sct",
                        "code": "195967001",
                        "display": "Asthma",
                    }
                ],
                "text": "Asthma",
            },
            "onsetDateTime": "2025-01-10T10:00:00Z",
            "recordedDate": "2025-01-10T11:00:00Z",
        }

        condition = map_fhir_condition(
            resource=resource,
            patient_id=patient.patient_id,
            encounter_id=encounter.encounter_id,
            source="synthea",
        )

        saved_condition = save_condition(
            db=db,
            condition=condition,
        )

        print("Condition persisted successfully")
        print(
            "SIGNAL condition_id:",
            saved_condition.condition_id,
        )
        print(
            "Source condition ID:",
            saved_condition.source_condition_id,
        )
        print(
            "Linked patient_id:",
            saved_condition.patient_id,
        )
        print(
            "Linked encounter_id:",
            saved_condition.encounter_id,
        )

    finally:
        db.close()


if __name__ == "__main__":
    main()