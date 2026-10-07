"""Prepare the configured controlled Texas measles MVP patient."""

from datetime import datetime, timezone

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from backend.app.database import SessionLocal
from backend.app.models.audit_event import AuditEvent
from backend.app.models.candidate import Candidate
from backend.app.models.case import Case
from backend.app.models.clinical_document import ClinicalDocument
from backend.app.models.condition import Condition
from backend.app.models.encounter import Encounter
from backend.app.models.lab_result import LabResult
from backend.app.models.observation import Observation
from backend.app.models.patient import Patient
from backend.app.config.demo import DEMO_FACILITY_ID, DEMO_PATIENT_SOURCE_ID


PATIENT_SOURCE_ID = DEMO_PATIENT_SOURCE_ID
LEGACY_PATIENT_SOURCE_ID = "MEASLES-MVP-001"
LEGACY_PATIENT_SOURCE = "signal_demo"
EVENT_TIME = datetime(2026, 10, 3, 10, 0, tzinfo=timezone.utc)


def _one_or_none(rows, description: str):
    if len(rows) > 1:
        raise ValueError(f"Expected at most one {description}; found {len(rows)}.")
    return rows[0] if rows else None


def remove_legacy_demo_patient(db: Session) -> bool:
    """Remove the prior standalone demo patient only when no workflow uses it."""
    patient = (
        db.query(Patient)
        .filter(
            Patient.source == LEGACY_PATIENT_SOURCE,
            Patient.source_patient_id == LEGACY_PATIENT_SOURCE_ID,
        )
        .one_or_none()
    )
    if patient is None:
        return False

    patient_id = str(patient.patient_id)
    candidates = db.query(Candidate).filter(Candidate.patient_id == patient_id).all()
    cases = []
    if inspect(db.get_bind()).has_table(Case.__tablename__):
        cases = [
            item
            for item in db.query(Case).all()
            if str((item.patient or {}).get("patient_id") or "") == patient_id
        ]
    audit_events = []
    if inspect(db.get_bind()).has_table(AuditEvent.__tablename__):
        audit_events = (
            db.query(AuditEvent)
            .filter(AuditEvent.entity_id == patient_id)
            .all()
        )
    references = {
        "candidates": candidates,
        "cases": cases,
        "audit events": audit_events,
    }
    referenced_by = [name for name, rows in references.items() if rows]
    if referenced_by:
        raise ValueError(
            f"Refusing to remove {LEGACY_PATIENT_SOURCE_ID}; referenced by "
            + ", ".join(referenced_by)
            + "."
        )

    db.query(LabResult).filter(LabResult.patient_id == patient.patient_id).delete(
        synchronize_session=False
    )
    db.query(Observation).filter(
        Observation.patient_id == patient.patient_id
    ).delete(synchronize_session=False)
    db.query(Condition).filter(
        Condition.patient_id == patient.patient_id
    ).delete(synchronize_session=False)
    db.query(ClinicalDocument).filter(
        ClinicalDocument.patient_id == patient.patient_id
    ).delete(synchronize_session=False)
    db.query(Encounter).filter(
        Encounter.patient_id == patient.patient_id
    ).delete(synchronize_session=False)
    db.delete(patient)
    db.flush()
    return True


def seed_measles_mvp_patient(db: Session) -> Patient:
    """Update the existing configured demo patient, without adding a patient."""
    patient = _one_or_none(
        db.query(Patient)
        .filter(Patient.source_patient_id == PATIENT_SOURCE_ID)
        .all(),
        f"canonical patient with source_patient_id={PATIENT_SOURCE_ID}",
    )
    if patient is None:
        raise ValueError(
            f"Canonical patient {PATIENT_SOURCE_ID} must already exist; "
            "this seed never creates patients."
        )

    patient.address_line = "100 Demo Way"
    patient.city = "Austin"
    patient.county = "Travis"
    patient.state = "TX"
    patient.postal_code = "78701"

    lab_result = _one_or_none(
        db.query(LabResult)
        .filter(
            LabResult.patient_id == patient.patient_id,
            LabResult.test_display.ilike("%Measles IgM%"),
        )
        .all(),
        f"Measles IgM lab result for {PATIENT_SOURCE_ID}",
    )
    if lab_result is None:
        raise ValueError(
            f"No existing Measles IgM lab result is available for {PATIENT_SOURCE_ID}."
        )

    observation = _one_or_none(
        list(lab_result.observations),
        f"observation linked to {PATIENT_SOURCE_ID}'s Measles IgM lab",
    )
    if observation is None:
        raise ValueError(
            f"No observation is linked to {PATIENT_SOURCE_ID}'s Measles IgM lab."
        )

    encounter = (
        db.query(Encounter)
        .filter(Encounter.encounter_id == lab_result.encounter_id)
        .one_or_none()
        if lab_result.encounter_id
        else None
    )
    if encounter is None:
        raise ValueError(
            f"No existing encounter is linked to {PATIENT_SOURCE_ID}'s Measles IgM lab."
        )

    encounter.facility_id = DEMO_FACILITY_ID
    encounter.start_time = EVENT_TIME
    observation.value_numeric = None
    observation.value_text = "Positive"
    observation.unit = None
    observation.value_code = None
    observation.effective_time = EVENT_TIME
    observation.status = observation.status or "final"
    lab_result.effective_time = EVENT_TIME
    lab_result.issued_time = EVENT_TIME
    lab_result.conclusion = "Positive"
    lab_result.report_status = lab_result.report_status or "final"
    db.flush()
    return patient


def main() -> None:
    db = SessionLocal()
    try:
        with db.begin():
            legacy_removed = remove_legacy_demo_patient(db)
            patient = seed_measles_mvp_patient(db)
            patient_id = patient.patient_id
        print(
            f"Prepared {PATIENT_SOURCE_ID} (patient_id={patient_id}); "
            f"legacy demo removed={legacy_removed}"
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
