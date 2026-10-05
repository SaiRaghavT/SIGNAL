from datetime import datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import Session

from backend.app.canonical.query_service import get_patient_context
from backend.app.database import get_db
from backend.app.detection.adapter import canonical_context_to_detection_input
from backend.app.detection.structured_trigger import detect_structured_triggers
from backend.app.jurisdiction.models import JurisdictionInput
from backend.app.jurisdiction.resolver import resolve_jurisdiction
from backend.app.main import app
from backend.app.models.candidate import Candidate
from backend.app.models.clinical_document import ClinicalDocument
from backend.app.models.condition import Condition
from backend.app.models.encounter import Encounter
from backend.app.models.follow_up import FollowUp
from backend.app.models.lab_result import LabResult, lab_result_observations
from backend.app.models.observation import Observation
from backend.app.models.patient import Patient
from backend.app.rules.resolver import resolve_rule
from backend.scripts.seed_measles_mvp import (
    DEMO_FACILITY_ID,
    EVENT_TIME,
    LEGACY_PATIENT_SOURCE,
    LEGACY_PATIENT_SOURCE_ID,
    PATIENT_SOURCE_ID,
    remove_legacy_demo_patient,
    seed_measles_mvp_patient,
)


def _session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    for model in (
        Patient,
        Encounter,
        Condition,
        Observation,
        LabResult,
        ClinicalDocument,
        Candidate,
        FollowUp,
    ):
        model.__table__.create(engine)
    lab_result_observations.create(engine)
    return Session(engine)


def _create_existing_hl7_patient(db: Session) -> Patient:
    patient = Patient(
        source_patient_id=PATIENT_SOURCE_ID,
        first_name="JOHN",
        last_name="DOE",
        state=None,
        source="hl7",
        source_resource="PID",
    )
    db.add(patient)
    db.flush()
    encounter = Encounter(
        source_encounter_id=f"{PATIENT_SOURCE_ID}-ENCOUNTER",
        patient_id=patient.patient_id,
        facility_id="ER^01^01",
        start_time=None,
        source="hl7",
        source_resource="PV1",
    )
    db.add(encounter)
    db.flush()
    observation = Observation(
        source_observation_id=f"{PATIENT_SOURCE_ID}-OBSERVATION",
        patient_id=patient.patient_id,
        encounter_id=encounter.encounter_id,
        observation_code="TEST001",
        observation_system="LN",
        observation_display="Measles IgM",
        value_numeric=1.25,
        unit="INDEX",
        source="hl7",
        source_resource="OBX",
    )
    lab_result = LabResult(
        source_lab_result_id=f"{PATIENT_SOURCE_ID}-LAB",
        patient_id=patient.patient_id,
        encounter_id=encounter.encounter_id,
        test_code="13950-1",
        test_system="LN",
        test_display="Measles IgM",
        source="hl7",
        source_resource="OBR",
        observations=[observation],
    )
    db.add_all([observation, lab_result])
    db.flush()
    return patient


def test_seed_updates_existing_hl7_patient_and_removes_unreferenced_legacy_demo():
    db = _session()
    try:
        patient = _create_existing_hl7_patient(db)
        legacy_patient = Patient(
            source_patient_id=LEGACY_PATIENT_SOURCE_ID,
            source=LEGACY_PATIENT_SOURCE,
            source_resource="Patient",
        )
        db.add(legacy_patient)
        db.flush()
        db.add(
            Encounter(
                source_encounter_id=f"{LEGACY_PATIENT_SOURCE_ID}-ENCOUNTER",
                patient_id=legacy_patient.patient_id,
                facility_id=DEMO_FACILITY_ID,
                start_time=EVENT_TIME,
                source=LEGACY_PATIENT_SOURCE,
                source_resource="Encounter",
            )
        )
        db.commit()

        assert remove_legacy_demo_patient(db) is True
        seeded = seed_measles_mvp_patient(db)
        assert seeded.patient_id == patient.patient_id
        assert seeded.state == "TX"
        db.commit()
        assert db.query(Patient).filter_by(
            source_patient_id=PATIENT_SOURCE_ID
        ).count() == 1
        assert db.query(Patient).filter_by(
            source=LEGACY_PATIENT_SOURCE,
            source_patient_id=LEGACY_PATIENT_SOURCE_ID,
        ).count() == 0
        assert db.query(Encounter).filter_by(
            patient_id=legacy_patient.patient_id
        ).count() == 0
        context = get_patient_context(db, patient.patient_id)
        assert context["patient"]["source_patient_id"] == PATIENT_SOURCE_ID
        assert context["patient"]["first_name"] == "JOHN"
        assert context["patient"]["address"]["state"] == "TX"
        assert context["patient"]["address"]["county"] == "Travis"
        assert context["encounters"][0]["facility_id"] == DEMO_FACILITY_ID
        assert context["encounters"][0]["start_time"]
        assert context["lab_results"][0]["effective_time"]
        assert context["lab_results"][0]["test"]["display"] == "Measles IgM"
        assert (
            context["lab_results"][0]["observations"][0]["value"]["text"]
            == "Positive"
        )
        assert (
            context["lab_results"][0]["observations"][0]["value"]["numeric"]
            is None
        )

        signals = detect_structured_triggers(
            canonical_context_to_detection_input(context)
        )
        assert any(signal["disease_id"] == "measles" for signal in signals)

        jurisdiction = resolve_jurisdiction(
            JurisdictionInput(
                candidate_id=str(patient.patient_id),
                patient_state=context["patient"]["address"]["state"],
                patient_county=context["patient"]["address"]["county"],
                facility_state=None,
                facility_county=None,
                disease="measles",
            )
        )
        assert jurisdiction.status == "RESOLVED"
        assert jurisdiction.jurisdiction == "TX"
        assert resolve_rule("measles", jurisdiction.jurisdiction)["rule_id"] == (
            "MEASLES-TX"
        )

        def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db
        try:
            client = TestClient(app)
            listed = client.get(
                "/api/canonical/patients",
                params={"search": PATIENT_SOURCE_ID, "page": 1, "page_size": 10},
            )
            assert listed.status_code == 200
            items = listed.json()["items"]
            assert len(items) == 1
            item = items[0]
            assert item["source_patient_id"] == PATIENT_SOURCE_ID
            assert item["first_name"] == "JOHN"
            assert item["condition"] == "Measles"
            assert item["deadline"]["disease"] == "measles"
            assert item["deadline"]["jurisdiction"] == "TX"
            assert item["deadline"]["rule_id"] == "MEASLES-TX"
            assert datetime.fromisoformat(
                item["deadline"]["deadline"].replace("Z", "+00:00")
            ) == EVENT_TIME + timedelta(hours=24)

            detail = client.get(
                f"/api/canonical/patients/{UUID(item['patient_id'])}"
            )
            assert detail.status_code == 200
            assert detail.json()["patient"]["source_patient_id"] == PATIENT_SOURCE_ID
            assert (
                detail.json()["lab_results"][0]["observations"][0]["value"]["text"]
                == "Positive"
            )
        finally:
            app.dependency_overrides.pop(get_db, None)
    finally:
        db.close()


def test_legacy_patient_cleanup_refuses_downstream_candidate_reference():
    db = _session()
    try:
        legacy_patient = Patient(
            source_patient_id=LEGACY_PATIENT_SOURCE_ID,
            source=LEGACY_PATIENT_SOURCE,
            source_resource="Patient",
        )
        db.add(legacy_patient)
        db.flush()
        db.add(
            Candidate(
                candidate_id=str(uuid4()),
                detection_key="legacy-patient-reference",
                patient_id=str(legacy_patient.patient_id),
                disease_id="measles",
                detection_source="test",
            )
        )
        db.commit()

        with pytest.raises(ValueError, match="referenced by candidates"):
            remove_legacy_demo_patient(db)
        assert db.query(Patient).filter_by(
            patient_id=legacy_patient.patient_id
        ).one()
    finally:
        db.close()
