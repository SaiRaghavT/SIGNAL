from backend.app.canonical.document_mapper import (
    map_fhir_document_reference,
)
from backend.app.canonical.persistence import (
    save_clinical_document,
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
            "resourceType": "DocumentReference",
            "id": "document-test-001",
            "status": "current",
            "type": {
                "coding": [
                    {
                        "system": "http://loinc.org",
                        "code": "34133-9",
                        "display": "Summary of episode note",
                    }
                ]
            },
            "subject": {
                "reference": "Patient/patient-test-001",
            },
            "date": "2025-01-10T11:00:00Z",
            "author": [
                {
                    "reference": (
                        "Practitioner/practitioner-001"
                    ),
                }
            ],
            "description": "Clinical summary",
            "content": [
                {
                    "attachment": {
                        "contentType": "application/pdf",
                        "url": (
                            "https://example.org/"
                            "document.pdf"
                        ),
                    }
                }
            ],
        }

        document = map_fhir_document_reference(
            resource=resource,
            patient_id=patient.patient_id,
            encounter_id=encounter.encounter_id,
            source="synthea",
        )

        saved_document = save_clinical_document(
            db=db,
            document=document,
        )

        print("ClinicalDocument persisted successfully")
        print(
            "SIGNAL document_id:",
            saved_document.document_id,
        )
        print(
            "Source document ID:",
            saved_document.source_document_id,
        )
        print(
            "Linked patient_id:",
            saved_document.patient_id,
        )
        print(
            "Linked encounter_id:",
            saved_document.encounter_id,
        )
        print(
            "Document type:",
            saved_document.document_type,
        )
        print(
            "Content type:",
            saved_document.content_type,
        )

    finally:
        db.close()


if __name__ == "__main__":
    main()