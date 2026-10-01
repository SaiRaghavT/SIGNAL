from sqlalchemy import select

from backend.app.database import SessionLocal
from backend.app.models.patient import Patient
from backend.app.provenance.provenance import get_provenance


def test_real_patient_provenance():

    db = SessionLocal()

    try:
        patient = db.execute(
            select(Patient)
            .where(Patient.source == "synthea")
            .limit(1)
        ).scalar_one_or_none()

        assert patient is not None, (
            "No Synthea patient found in the database."
        )

        result = get_provenance(
            patient,
            "Patient",
        )

        assert result["entity_type"] == "Patient"
        assert result["source"] == "synthea"
        assert result["source_id"] == patient.source_patient_id
        assert result["source_resource"] == "Patient"

    finally:
        db.close()