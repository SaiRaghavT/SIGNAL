from backend.app.canonical.patient_mapper import map_fhir_patient
from backend.app.canonical.persistence import save_patient
from backend.app.database import SessionLocal


def main():
    resource = {
        "resourceType": "Patient",
        "id": "synthea-test-001",
        "birthDate": "1990-05-12",
        "gender": "male",
        "address": [
            {
                "line": ["123 Main St"],
                "city": "Austin",
                "district": "Travis",
                "state": "Texas",
                "postalCode": "78701",
            }
        ],
    }

    patient = map_fhir_patient(
        resource,
        source="synthea",
    )

    db = SessionLocal()

    try:
        saved_patient = save_patient(
            db,
            patient,
        )

        print("Patient persisted successfully")
        print("SIGNAL patient_id:", saved_patient.patient_id)
        print("Source patient ID:", saved_patient.source_patient_id)
        print("Source:", saved_patient.source)

    finally:
        db.close()


if __name__ == "__main__":
    main()