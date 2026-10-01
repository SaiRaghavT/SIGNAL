from backend.app.canonical.lab_result_mapper import (
    map_fhir_diagnostic_report,
)
from backend.app.canonical.persistence import (
    save_lab_result,
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
            "resourceType": "DiagnosticReport",
            "id": "report-test-001",
            "status": "final",
            "category": [
                {
                    "coding": [
                        {
                            "system": (
                                "http://terminology.hl7.org/"
                                "CodeSystem/v2-0074"
                            ),
                            "code": "LAB",
                            "display": "Laboratory",
                        }
                    ]
                }
            ],
            "code": {
                "coding": [
                    {
                        "system": "http://loinc.org",
                        "code": "58410-2",
                        "display": "CBC panel",
                    }
                ]
            },
            "effectiveDateTime": (
                "2025-01-10T10:00:00Z"
            ),
            "issued": "2025-01-10T11:00:00Z",
            "performer": [
                {
                    "reference": "Organization/lab-001",
                }
            ],
            "conclusion": "Normal CBC",
            "result": [
                {
                    "reference": (
                        "Observation/"
                        "observation-test-001"
                    )
                }
            ],
        }

        lab_result, observation_ids = (
            map_fhir_diagnostic_report(
                resource=resource,
                patient_id=patient.patient_id,
                encounter_id=encounter.encounter_id,
                source="synthea",
            )
        )

        saved_lab_result = save_lab_result(
            db=db,
            lab_result=lab_result,
            observation_source_ids=observation_ids,
        )

        print("LabResult persisted successfully")
        print(
            "SIGNAL lab_result_id:",
            saved_lab_result.lab_result_id,
        )
        print(
            "Source lab result ID:",
            saved_lab_result.source_lab_result_id,
        )
        print(
            "Linked patient_id:",
            saved_lab_result.patient_id,
        )
        print(
            "Linked encounter_id:",
            saved_lab_result.encounter_id,
        )
        print(
            "Linked observations:",
            [
                observation.source_observation_id
                for observation
                in saved_lab_result.observations
            ],
        )

    finally:
        db.close()


if __name__ == "__main__":
    main()