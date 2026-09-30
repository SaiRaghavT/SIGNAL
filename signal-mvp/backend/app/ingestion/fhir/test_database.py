from sqlalchemy import func

from backend.app.database import SessionLocal

from backend.app.models.patient import Patient
from backend.app.models.encounter import Encounter
from backend.app.models.condition import Condition
from backend.app.models.observation import Observation
from backend.app.models.lab_result import LabResult
from backend.app.models.clinical_document import ClinicalDocument


def main():
    db = SessionLocal()

    try:
        # =====================================================
        # 1. Count canonical records
        # =====================================================

        patient_count = db.query(func.count(Patient.patient_id)).scalar()
        encounter_count = db.query(func.count(Encounter.encounter_id)).scalar()
        condition_count = db.query(func.count(Condition.condition_id)).scalar()
        observation_count = db.query(
            func.count(Observation.observation_id)
        ).scalar()
        lab_result_count = db.query(
            func.count(LabResult.lab_result_id)
        ).scalar()
        document_count = db.query(
            func.count(ClinicalDocument.document_id)
        ).scalar()

        print("SIGNAL PostgreSQL Database Verification")
        print("----------------------------------------")
        print(f"Patients:           {patient_count}")
        print(f"Encounters:         {encounter_count}")
        print(f"Conditions:         {condition_count}")
        print(f"Observations:       {observation_count}")
        print(f"Lab Results:        {lab_result_count}")
        print(f"Clinical Documents: {document_count}")

        total = (
            patient_count
            + encounter_count
            + condition_count
            + observation_count
            + lab_result_count
            + document_count
        )

        print(f"\nTotal canonical records: {total}")

        # =====================================================
        # 2. Verify patient → encounter relationship
        # =====================================================

        encounter = (
            db.query(Encounter)
            .order_by(Encounter.created_at)
            .first()
        )

        if encounter:
            patient = (
                db.query(Patient)
                .filter(
                    Patient.patient_id == encounter.patient_id
                )
                .first()
            )

            print("\nPatient → Encounter")
            print("------------------")
            print(f"Encounter ID: {encounter.encounter_id}")
            print(f"Patient ID:   {encounter.patient_id}")
            print(
                f"Patient found: "
                f"{'YES' if patient else 'NO'}"
            )

        # =====================================================
        # 3. Verify condition → patient + encounter
        # =====================================================

        condition = (
            db.query(Condition)
            .order_by(Condition.created_at)
            .first()
        )

        if condition:
            patient = (
                db.query(Patient)
                .filter(
                    Patient.patient_id == condition.patient_id
                )
                .first()
            )

            encounter = None

            if condition.encounter_id:
                encounter = (
                    db.query(Encounter)
                    .filter(
                        Encounter.encounter_id
                        == condition.encounter_id
                    )
                    .first()
                )

            print("\nCondition → Patient + Encounter")
            print("------------------------------")
            print(f"Condition ID: {condition.condition_id}")
            print(
                f"Patient found: "
                f"{'YES' if patient else 'NO'}"
            )
            print(
                f"Encounter found: "
                f"{'YES' if encounter else 'NO'}"
            )

        # =====================================================
        # 4. Verify observation → patient + encounter
        # =====================================================

        observation = (
            db.query(Observation)
            .order_by(Observation.created_at)
            .first()
        )

        if observation:
            patient = (
                db.query(Patient)
                .filter(
                    Patient.patient_id == observation.patient_id
                )
                .first()
            )

            encounter = None

            if observation.encounter_id:
                encounter = (
                    db.query(Encounter)
                    .filter(
                        Encounter.encounter_id
                        == observation.encounter_id
                    )
                    .first()
                )

            print("\nObservation → Patient + Encounter")
            print("--------------------------------")
            print(
                f"Observation ID: "
                f"{observation.observation_id}"
            )
            print(
                f"Patient found: "
                f"{'YES' if patient else 'NO'}"
            )
            print(
                f"Encounter found: "
                f"{'YES' if encounter else 'NO'}"
            )

        # =====================================================
        # 5. Verify LabResult → observations
        # =====================================================

        lab_result = (
    db.query(LabResult)
    .filter(LabResult.observations.any())
    .order_by(LabResult.created_at)
    .first()
)

        if lab_result:
            linked_observations = lab_result.observations

            patient = (
                db.query(Patient)
                .filter(
                    Patient.patient_id == lab_result.patient_id
                )
                .first()
            )

            encounter = None

            if lab_result.encounter_id:
                encounter = (
                    db.query(Encounter)
                    .filter(
                        Encounter.encounter_id
                        == lab_result.encounter_id
                    )
                    .first()
                )

            print("\nLabResult → Patient + Encounter + Observations")
            print("-----------------------------------------------")
            print(
                f"Lab Result ID: "
                f"{lab_result.lab_result_id}"
            )
            print(
                f"Patient found: "
                f"{'YES' if patient else 'NO'}"
            )
            print(
                f"Encounter found: "
                f"{'YES' if encounter else 'NO'}"
            )
            print(
                f"Linked observations: "
                f"{len(linked_observations)}"
            )

            for linked_observation in linked_observations[:5]:
                print(
                    f"  - "
                    f"{linked_observation.source_observation_id}"
                )

        # =====================================================
        # 6. Verify ClinicalDocument → patient + encounter
        # =====================================================

        document = (
            db.query(ClinicalDocument)
            .order_by(ClinicalDocument.created_at)
            .first()
        )

        if document:
            patient = (
                db.query(Patient)
                .filter(
                    Patient.patient_id == document.patient_id
                )
                .first()
            )

            encounter = None

            if document.encounter_id:
                encounter = (
                    db.query(Encounter)
                    .filter(
                        Encounter.encounter_id
                        == document.encounter_id
                    )
                    .first()
                )

            print("\nClinicalDocument → Patient + Encounter")
            print("--------------------------------------")
            print(
                f"Document ID: "
                f"{document.document_id}"
            )
            print(
                f"Patient found: "
                f"{'YES' if patient else 'NO'}"
            )
            print(
                f"Encounter found: "
                f"{'YES' if encounter else 'NO'}"
            )

        # =====================================================
        # 7. Final verification
        # =====================================================

        expected = {
            "patients": 1,
            "encounters": 18,
            "conditions": 25,
            "observations": 116,
            "lab_results": 37,
            "clinical_documents": 18,
        }

        actual = {
            "patients": patient_count,
            "encounters": encounter_count,
            "conditions": condition_count,
            "observations": observation_count,
            "lab_results": lab_result_count,
            "clinical_documents": document_count,
        }

        print("\nExpected vs Actual")
        print("------------------")

        all_counts_match = True

        for resource_type in expected:
            expected_count = expected[resource_type]
            actual_count = actual[resource_type]

            status = "PASS" if expected_count == actual_count else "FAIL"

            print(
                f"{resource_type:<20} "
                f"expected={expected_count:<4} "
                f"actual={actual_count:<4} "
                f"[{status}]"
            )

            if expected_count != actual_count:
                all_counts_match = False

        print()

        if all_counts_match:
            print("DATABASE VERIFICATION PASSED")
        else:
            print("DATABASE VERIFICATION FAILED")

    finally:
        db.close()


if __name__ == "__main__":
    main()