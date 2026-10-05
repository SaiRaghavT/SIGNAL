from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.canonical.query_service import list_patients
from backend.app.models.candidate import Candidate
from backend.app.models.condition import Condition
from backend.app.models.encounter import Encounter
from backend.app.models.lab_result import LabResult, lab_result_observations
from backend.app.models.observation import Observation
from backend.app.models.patient import Patient


def _session() -> Session:
    engine = create_engine("sqlite://")
    Patient.__table__.create(engine)
    Encounter.__table__.create(engine)
    Condition.__table__.create(engine)
    Observation.__table__.create(engine)
    LabResult.__table__.create(engine)
    lab_result_observations.create(engine)
    Candidate.__table__.create(engine)
    return Session(engine)


def test_list_patients_returns_real_related_fields_and_pagination():
    db = _session()
    first = Patient(
        patient_id=uuid4(), source_patient_id="source-100", first_name="Ada",
        last_name="Lovelace", date_of_birth=date(1815, 12, 10),
        source="test", source_resource="Patient",
    )
    second = Patient(
        patient_id=uuid4(), source_patient_id="source-200", first_name="Grace",
        last_name="Hopper", date_of_birth=date(1906, 12, 9),
        source="test", source_resource="Patient",
    )
    db.add_all([first, second])
    db.flush()
    db.add(Encounter(
        encounter_id=uuid4(), source_encounter_id="enc-100", patient_id=first.patient_id,
        facility_id="Facility A", start_time=datetime(2026, 1, 2, tzinfo=timezone.utc),
        source="test", source_resource="Encounter",
    ))
    db.add(Condition(
        condition_id=uuid4(), source_condition_id="condition-100", patient_id=first.patient_id,
        condition_system="http://snomed.info/sct", condition_code="14168008",
        source="test", source_resource="Condition",
    ))
    db.commit()

    result = list_patients(db, page=1, page_size=1)

    assert result["total"] == 2
    assert result["pages"] == 2
    assert len(result["items"]) == 1
    listed = result["items"][0]
    assert listed["patient_id"] in {str(first.patient_id), str(second.patient_id)}
    other_page = list_patients(db, page=2, page_size=1)
    assert other_page["items"][0]["patient_id"] != listed["patient_id"]
    assert result["facilities"] == ["Facility A"]

    filtered = list_patients(db, search="source-100", facility="Facility A")
    assert filtered["total"] == 1
    assert filtered["items"][0]["patient_id"] == str(first.patient_id)
    assert filtered["items"][0]["conditions"] == [
        {"code": "14168008", "display": None}
    ]
    assert filtered["items"][0]["condition"] == "Measles"
    assert "severity" not in filtered["items"][0]
    assert "deadline" in filtered["items"][0]
    db.close()


def test_list_patients_surfaces_canonical_measles_lab_test_when_no_condition():
    db = _session()
    patient = Patient(
        patient_id=uuid4(),
        source_patient_id="source-lab",
        source="test",
        source_resource="Patient",
    )
    db.add(patient)
    db.flush()
    db.add(LabResult(
        lab_result_id=uuid4(),
        source_lab_result_id="lab-measles",
        patient_id=patient.patient_id,
        test_display="Measles IgM",
        source="test",
        source_resource="DiagnosticReport",
    ))
    db.commit()

    result = list_patients(db)

    assert result["items"][0]["condition"] == "Measles"
    assert result["items"][0]["deadline"] is None
    assert "not classified as positive" in result["items"][0]["deadline_reason"]
    db.close()


def test_list_patients_calculates_deadline_for_positive_measles_lab():
    db = _session()
    event_time = datetime(2026, 9, 30, 12, tzinfo=timezone.utc)
    patient = Patient(
        patient_id=uuid4(),
        source_patient_id="source-positive-measles-lab",
        state="TX",
        source="test",
        source_resource="Patient",
    )
    observation = Observation(
        observation_id=uuid4(),
        source_observation_id="positive-measles-observation",
        patient_id=patient.patient_id,
        observation_display="Measles IgM",
        value_text="Positive",
        effective_time=event_time,
        source="test",
        source_resource="Observation",
    )
    lab_result = LabResult(
        lab_result_id=uuid4(),
        source_lab_result_id="positive-measles-lab",
        patient_id=patient.patient_id,
        test_display="Measles IgM",
        effective_time=event_time,
        source="test",
        source_resource="DiagnosticReport",
        observations=[observation],
    )
    db.add_all([patient, observation, lab_result])
    db.commit()

    result = list_patients(db)
    deadline = result["items"][0]["deadline"]

    assert deadline["deadline"] == event_time + timedelta(hours=24)
    assert deadline["disease"] == "measles"
    assert deadline["jurisdiction"] == "TX"
    assert deadline["rule_id"] == "MEASLES-TX"
    db.close()


def test_list_patients_reuses_persisted_candidate_deadline():
    db = _session()
    patient = Patient(
        patient_id=uuid4(),
        source_patient_id="source-persisted-deadline",
        state="TX",
        source="test",
        source_resource="Patient",
    )
    candidate = Candidate(
        candidate_id=str(uuid4()),
        detection_key="persisted-measles-deadline",
        patient_id=str(patient.patient_id),
        disease_id="measles",
        jurisdiction="TX",
        detection_source="test",
        deadline=datetime(2026, 10, 5, 12, tzinfo=timezone.utc),
        severity="HIGH",
    )
    db.add_all([patient, candidate])
    db.commit()

    result = list_patients(db)
    deadline = result["items"][0]["deadline"]

    assert deadline["status"] == "PERSISTED"
    assert deadline["deadline"].date().isoformat() == "2026-10-05"
    assert deadline["disease"] == "measles"
    assert deadline["jurisdiction"] == "TX"
    assert deadline["rule_id"] == "MEASLES-TX"
    assert deadline["urgency"] == "HIGH"
    db.close()


def test_list_patients_calculates_measles_deadline_from_condition_event():
    db = _session()
    event_time = datetime(2026, 9, 30, 12, tzinfo=timezone.utc)
    patient = Patient(
        patient_id=uuid4(),
        source_patient_id="source-measles-deadline",
        state="TX",
        source="test",
        source_resource="Patient",
    )
    db.add(patient)
    db.flush()
    db.add(Condition(
        condition_id=uuid4(),
        source_condition_id="condition-measles-deadline",
        patient_id=patient.patient_id,
        condition_system="http://snomed.info/sct",
        condition_code="14168008",
        onset_time=event_time,
        source="test",
        source_resource="Condition",
    ))
    db.commit()

    result = list_patients(db)
    deadline = result["items"][0]["deadline"]

    assert deadline["deadline"] == event_time + timedelta(hours=24)
    assert deadline["status"] == "CALCULATED"
    assert deadline["disease"] == "measles"
    assert deadline["jurisdiction"] == "TX"
    assert deadline["rule_id"] == "MEASLES-TX"
    assert deadline["reporting_timing"] == "HOURS"
    assert deadline["reporting_method"] == "CRF"
    db.close()


def test_list_patients_does_not_calculate_measles_deadline_for_other_condition():
    db = _session()
    patient = Patient(
        patient_id=uuid4(),
        source_patient_id="source-non-measles",
        state="TX",
        source="test",
        source_resource="Patient",
    )
    db.add(patient)
    db.flush()
    db.add(Condition(
        condition_id=uuid4(),
        source_condition_id="condition-non-measles",
        patient_id=patient.patient_id,
        condition_system="http://snomed.info/sct",
        condition_code="123456",
        condition_display="Gingival disease",
        onset_time=datetime(2026, 9, 30, 12, tzinfo=timezone.utc),
        source="test",
        source_resource="Condition",
    ))
    db.commit()

    result = list_patients(db)

    assert result["items"][0]["deadline"] is None
    assert "No disease-specific" in result["items"][0]["deadline_reason"]
    db.close()


def test_list_patients_leaves_deadline_null_without_event_timestamp():
    db = _session()
    patient = Patient(
        patient_id=uuid4(),
        source_patient_id="source-measles-no-time",
        state="TX",
        source="test",
        source_resource="Patient",
    )
    db.add(patient)
    db.flush()
    db.add(Condition(
        condition_id=uuid4(),
        source_condition_id="condition-measles-no-time",
        patient_id=patient.patient_id,
        condition_system="http://snomed.info/sct",
        condition_code="14168008",
        source="test",
        source_resource="Condition",
    ))
    db.commit()

    result = list_patients(db)

    assert result["items"][0]["deadline"] is None
    assert "timestamp" in result["items"][0]["deadline_reason"]
    db.close()


def test_list_patients_returns_empty_page_for_no_matches():
    db = _session()
    result = list_patients(db, search="not-present")
    assert result["items"] == []
    assert result["total"] == 0
    assert result["pages"] == 0
    db.close()
