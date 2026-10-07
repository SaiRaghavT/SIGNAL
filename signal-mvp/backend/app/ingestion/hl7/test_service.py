from sqlalchemy import func, select

from backend.app.database import SessionLocal
from backend.app.ingestion.hl7.service import (
    ingest_hl7_message,
)
from backend.app.models.encounter import Encounter
from backend.app.models.lab_result import LabResult
from backend.app.models.observation import Observation
from backend.app.models.patient import Patient


SAMPLE_HL7 = (
    "MSH|^~\\&|SENDER|HOSPITAL|RECEIVER|PHA|"
    "202609281200||ORU^R01|MSG00001|P|2.5.1\r"
    "PID|1||PAT-HL7-TEST-001^^^HOSPITAL||"
    "PATIENT^SAMPLE||19850505|M\r"
    "PV1|1|I|ER^01^01||||"
    "12345^SMITH^JANE\r"
    "ORC|RE|ORDER-HL7-001\r"
    "OBR|1|ORDER-HL7-001|LAB-HL7-001|"
    "13950-1^Measles IgM^LN\r"
    "OBX|1|NM|TEST001^Measles IgM^LN|"
    "1|1.25|INDEX||||F"
)


def test_ingest_hl7_message():

    db = SessionLocal()

    try:
        result = ingest_hl7_message(
            db=db,
            message=SAMPLE_HL7,
        )

        assert result["status"] == "success"
        assert result["source"] == "hl7"
        assert result["message_type"] == "ORU^R01"

        assert result["counts"]["patients"] == 1
        assert result["counts"]["encounters"] == 1
        assert result["counts"]["observations"] == 1
        assert result["counts"]["lab_results"] == 1

        patient = (
            db.execute(
                select(Patient).where(
                    Patient.source == "hl7",
                    Patient.source_patient_id
                    == "PAT-HL7-TEST-001",
                )
            )
            .scalar_one()
        )

        encounter = (
            db.execute(
                select(Encounter).where(
                    Encounter.source == "hl7",
                    Encounter.source_encounter_id
                    == "hl7-encounter-PAT-HL7-TEST-001",
                )
            )
            .scalar_one()
        )

        observation = (
            db.execute(
                select(Observation).where(
                    Observation.source == "hl7",
                    Observation.source_observation_id
                    == "1",
                )
            )
            .scalar_one()
        )

        lab_result = (
            db.execute(
                select(LabResult).where(
                    LabResult.source == "hl7",
                    LabResult.source_lab_result_id
                    == "ORDER-HL7-001",
                )
            )
            .scalar_one()
        )

        assert patient.first_name == "SAMPLE"
        assert patient.last_name == "PATIENT"
        assert encounter.patient_id == patient.patient_id
        assert observation.patient_id == patient.patient_id
        assert observation.encounter_id == encounter.encounter_id

        assert lab_result.patient_id == patient.patient_id
        assert lab_result.encounter_id == encounter.encounter_id

        assert len(lab_result.observations) == 1
        assert (
            lab_result.observations[0].observation_id
            == observation.observation_id
        )

    finally:
        db.close()


def test_invalid_hl7_is_rejected_before_persistence():

    invalid_hl7 = (
        "MSH|^~\\&|SENDER|HOSPITAL|RECEIVER|PHA|"
        "202609281200||ORU^R01|MSG-INVALID|P|2.5.1\r"
        "PID|1||||PATIENT^SAMPLE||19850505|M"
    )

    db = SessionLocal()

    try:
        try:
            ingest_hl7_message(
                db=db,
                message=invalid_hl7,
            )

            assert False, (
                "Invalid HL7 message should have been rejected."
            )

        except ValueError as exc:
            assert (
                "HL7 data quality validation failed"
                in str(exc)
            )

        patient = (
            db.execute(
                select(Patient).where(
                    Patient.source == "hl7",
                    Patient.source_patient_id
                    == "PATIENT",
                )
            )
            .scalar_one_or_none()
        )

        assert patient is None

    finally:
        db.close()
