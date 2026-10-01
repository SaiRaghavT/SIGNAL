from datetime import datetime

from backend.app.canonical.encounter_mapper import map_fhir_encounter
from backend.app.canonical.persistence import save_encounter
from backend.app.database import SessionLocal
from backend.app.models.patient import Patient


def main():
    db = SessionLocal()

    try:
        # Find the Patient that we already inserted.
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

        resource = {
            "resourceType": "Encounter",
            "id": "encounter-test-001",
            "status": "finished",
            "class": {
                "code": "AMB",
                "display": "ambulatory",
            },
            "period": {
                "start": "2025-01-10T10:00:00Z",
                "end": "2025-01-10T11:00:00Z",
            },
            "serviceProvider": {
                "reference": "Organization/hospital-001",
            },
        }

        encounter = map_fhir_encounter(
            resource=resource,
            patient_id=patient.patient_id,
            source="synthea",
        )

        saved_encounter = save_encounter(
            db=db,
            encounter=encounter,
        )

        print("Encounter persisted successfully")
        print("SIGNAL encounter_id:", saved_encounter.encounter_id)
        print(
            "Source encounter ID:",
            saved_encounter.source_encounter_id,
        )
        print(
            "Linked patient_id:",
            saved_encounter.patient_id,
        )

    finally:
        db.close()


if __name__ == "__main__":
    main()