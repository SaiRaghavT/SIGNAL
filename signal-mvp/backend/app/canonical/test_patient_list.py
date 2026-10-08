from datetime import date, datetime, timedelta, timezone
import json
from uuid import UUID, uuid4

from sqlalchemy import create_engine
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.canonical.query_service import list_patients
from backend.app.models.candidate import Candidate
from backend.app.models.case import Case
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
    with engine.begin() as connection:
        connection.execute(text("""
            CREATE TABLE cases (
                case_id CHAR(32) PRIMARY KEY, candidate_id VARCHAR(255) NOT NULL,
                patient TEXT NOT NULL, facility TEXT NOT NULL, provider TEXT NOT NULL,
                disease VARCHAR(100), clinical_evidence TEXT NOT NULL,
                laboratory_evidence TEXT NOT NULL, ai_evidence TEXT NOT NULL,
                report_fields TEXT NOT NULL, jurisdiction VARCHAR(100),
                jurisdiction_status VARCHAR(50) NOT NULL,
                reportability_decision VARCHAR(50) NOT NULL,
                reportability_evidence_status VARCHAR(100) NOT NULL,
                status VARCHAR(50) NOT NULL, submission_mode VARCHAR(20), final_decision VARCHAR(50),
                rule_id VARCHAR(255), deadline DATETIME, severity VARCHAR(20),
                warnings TEXT NOT NULL, created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
            )
        """))
    return Session(engine)


def test_list_patients_returns_real_related_fields_and_pagination():
    db = _session()
    first = Patient(
        patient_id=uuid4(), source_patient_id="source-100", first_name="Ada",
        last_name="Lovelace", date_of_birth=date(1815, 12, 10),
        state="TX",
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
    db.add(Encounter(
        encounter_id=uuid4(), source_encounter_id="enc-101", patient_id=first.patient_id,
        facility_id="Facility A", start_time=datetime(2026, 1, 3, tzinfo=timezone.utc),
        source="test", source_resource="Encounter",
    ))
    db.add(Condition(
        condition_id=uuid4(), source_condition_id="condition-100", patient_id=first.patient_id,
        condition_system="http://snomed.info/sct", condition_code="14168008",
        condition_display="Measles",
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

    filtered = list_patients(db, search="source-100", facility="Facility A", condition="MeAsLeS")
    assert filtered["total"] == 1
    assert filtered["items"][0]["patient_id"] == str(first.patient_id)
    assert filtered["items"][0]["conditions"] == [
        {"code": "14168008", "display": "Measles"}
    ]
    assert filtered["items"][0]["condition"] == "Measles"
    assert filtered["condition_filter"] == "Measles"
    assert filtered["items"][0]["last_encounter"].replace(tzinfo=timezone.utc) == datetime(2026, 1, 3, tzinfo=timezone.utc)
    assert "severity" not in filtered["items"][0]
    assert filtered["items"][0]["deadline"]["deadline"] == datetime(2026, 1, 3, tzinfo=timezone.utc)
    db.close()


def test_measles_worklist_is_texas_only_and_returns_patient_display_fields():
    db = _session()
    texas_patient = Patient(
        patient_id=uuid4(), source_patient_id="texas-source-id",
        first_name="Taylor", last_name="Patient", date_of_birth=date(1990, 3, 4),
        state="Texas", source="test", source_resource="Patient",
    )
    out_of_state_patient = Patient(
        patient_id=uuid4(), source_patient_id="other-state-source-id",
        first_name="Casey", last_name="Patient", state="CA",
        source="test", source_resource="Patient",
    )
    non_measles_patient = Patient(
        patient_id=uuid4(), source_patient_id="texas-non-measles-id",
        state="TX", source="test", source_resource="Patient",
    )
    db.add_all([texas_patient, out_of_state_patient, non_measles_patient])
    db.flush()
    db.add_all([
        Condition(
            condition_id=uuid4(), source_condition_id=f"measles-{index}",
            patient_id=patient.patient_id, condition_display="Measles",
            onset_time=datetime(2026, 9, 30, tzinfo=timezone.utc),
            source="test", source_resource="Condition",
        )
        for index, patient in enumerate((texas_patient, out_of_state_patient))
    ])
    db.add(Condition(
        condition_id=uuid4(), source_condition_id="non-measles-condition",
        patient_id=non_measles_patient.patient_id,
        condition_display="Seasonal allergy", source="test", source_resource="Condition",
    ))
    db.commit()

    result = list_patients(db, condition="measles")
    assert result["total"] == 1
    item = result["items"][0]
    assert item["patient_id"] == str(texas_patient.patient_id)
    assert item["first_name"] == "Taylor"
    assert item["last_name"] == "Patient"
    assert item["source_patient_id"] == "texas-source-id"
    assert "mrn" not in item
    assert item["date_of_birth"] == "1990-03-04"
    assert item["jurisdiction"] == "TX"
    assert item["deadline"] is not None
    assert item["deadline_reason"] is None
    assert str(out_of_state_patient.patient_id) not in {row["patient_id"] for row in result["items"]}
    assert str(non_measles_patient.patient_id) not in {row["patient_id"] for row in result["items"]}
    db.close()


def test_measles_list_returns_all_unique_patients_with_calculated_deadlines():
    db = _session()
    event_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
    patients = [
        Patient(
            patient_id=uuid4(),
            source_patient_id=f"measles-patient-{index}",
            state="TX",
            source="test",
            source_resource="Patient",
        )
        for index in range(57)
    ]
    db.add_all(patients)
    db.flush()
    db.add_all([
        Condition(
            condition_id=uuid4(),
            source_condition_id=f"measles-condition-{index}",
            patient_id=patient.patient_id,
            condition_display="Measles (disorder)",
            condition_system="http://snomed.info/sct",
            condition_code="14168008",
            onset_time=event_time + timedelta(minutes=index),
            recorded_time=event_time + timedelta(minutes=index),
            source="test",
            source_resource="Condition",
        )
        for index, patient in enumerate(patients)
    ])
    db.commit()

    result = list_patients(db, condition="measles", page_size=100)

    assert result["total"] == 57
    assert len(result["items"]) == 57
    assert len({item["patient_id"] for item in result["items"]}) == 57
    assert all(item["deadline"] is not None for item in result["items"])
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
    assert "No disease" in result["items"][0]["deadline_reason"]
    db.close()


def test_list_patients_calculates_deadline_from_positive_measles_lab_event():
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

    result = list_patients(db, condition="measles")
    deadline = result["items"][0]["deadline"]
    assert deadline["deadline"] == event_time
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

    result = list_patients(db, condition="measles")
    assert result["total"] == 1
    assert result["items"][0]["deadline"]["rule_id"] == "MEASLES-TX"
    assert result["items"][0]["deadline"]["deadline"] == datetime(2026, 10, 5, 12)
    db.close()


def test_candidate_explicit_clinical_event_time_is_used_without_using_created_at():
    db = _session()
    event_time = datetime(2026, 9, 30, 12, tzinfo=timezone.utc)
    patient = Patient(
        patient_id=uuid4(), source_patient_id="source-candidate-event",
        date_of_birth=date(1990, 1, 1), state="TX",
        source="test", source_resource="Patient",
    )
    candidate = Candidate(
        candidate_id=str(uuid4()), detection_key="candidate-event-time",
        patient_id=str(patient.patient_id), disease_id="measles", jurisdiction="TX",
        detection_source="test", evidence=[{"event_time": event_time.isoformat()}],
    )
    db.add_all([patient, candidate])
    db.commit()

    result = list_patients(db, condition="measles")
    deadline = result["items"][0]["deadline"]
    assert deadline["deadline"] == event_time
    assert deadline["rule_id"] == "MEASLES-TX"
    db.close()


def test_measles_case_only_qualifies_and_preserves_deadline_rule_distinction():
    db = _session()
    patient_id = UUID("910b69db-2c7d-47c1-88d2-18558376601d")
    deadline = datetime(2026, 10, 4, 15, 30, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    event_time = datetime(2026, 10, 3, 15, 30, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    patient = Patient(
        patient_id=patient_id, source_patient_id="TEST-MEASLES-001", first_name="SAMPLE",
        last_name="PATIENT", date_of_birth=date(1985, 5, 5), state="TX",
        source="test", source_resource="Patient",
    )
    candidate_id = str(uuid4())
    case_id = uuid4().hex
    db.add(patient)
    db.flush()
    db.add(Candidate(
        candidate_id=candidate_id, detection_key="sample-patient-measles",
        patient_id=str(patient_id), disease_id="measles", jurisdiction="TX",
        case_id=case_id, detection_source="LAB_RESULT", status="PROCESSED",
    ))
    observation = Observation(
        observation_id=uuid4(), source_observation_id="sample-patient-observation",
        patient_id=patient_id, observation_display="Measles IgM", value_text="Positive",
        effective_time=event_time, source="test", source_resource="Observation",
    )
    db.add_all([observation, LabResult(
        lab_result_id=uuid4(), source_lab_result_id="sample-patient-lab",
        patient_id=patient_id, test_display="Measles IgM", conclusion="Positive",
        effective_time=event_time, issued_time=event_time, source="test",
        source_resource="DiagnosticReport", observations=[observation],
    )])
    db.execute(text("""
        INSERT INTO cases (case_id, candidate_id, patient, facility, provider, disease,
            clinical_evidence, laboratory_evidence, ai_evidence, report_fields, jurisdiction,
            jurisdiction_status, reportability_decision, reportability_evidence_status, status,
            rule_id, deadline, warnings)
        VALUES (:case_id, :candidate_id, :patient, '{}', '{}', 'measles', '{}', '[]', '{}', '{}',
            'TX', 'RESOLVED', 'PROCEED_TO_RULES', 'SUPPORTED', 'NEEDS_REVIEW', 'MEASLES-003',
            :deadline, '[]')
    """), {
        "case_id": case_id, "candidate_id": candidate_id,
        "patient": json.dumps({"patient_id": str(patient_id)}),
        "deadline": deadline,
    })
    db.commit()

    result = list_patients(db, condition="measles", page_size=100)
    assert result["total"] == 1
    assert len({item["patient_id"] for item in result["items"]}) == 1
    john = result["items"][0]
    assert john["source_patient_id"] == "TEST-MEASLES-001"
    assert john["condition"] == "Measles"
    assert john["deadline"]["deadline"] == event_time.replace(tzinfo=timezone.utc)
    assert john["deadline"]["disease"] == "measles"
    assert john["deadline"]["jurisdiction"] == "TX"
    assert john["deadline"]["rule_id"] == "MEASLES-TX"
    assert db.query(Case).filter(Case.candidate_id == candidate_id).one().rule_id == "MEASLES-003"
    db.close()


def test_list_patients_calculates_independent_deadlines_from_condition_events():
    db = _session()
    event_times = [
        datetime(2026, 9, 30, 12, tzinfo=timezone.utc),
        datetime(2026, 10, 2, 7, 15, tzinfo=timezone.utc),
    ]
    patients = [
        Patient(
            patient_id=uuid4(),
            source_patient_id=f"source-measles-deadline-{index}",
            state="TX",
            source="test",
            source_resource="Patient",
        )
        for index in range(len(event_times))
    ]
    db.add_all(patients)
    db.flush()
    db.add_all([
        Condition(
            condition_id=uuid4(),
            source_condition_id=f"condition-measles-deadline-{index}",
            patient_id=patient.patient_id,
            condition_system="http://snomed.info/sct",
            condition_code="14168008",
            condition_display="Measles (disorder)",
            onset_time=event_time,
            recorded_time=event_time,
            source="test",
            source_resource="Condition",
        )
        for index, (patient, event_time) in enumerate(zip(patients, event_times))
    ])
    db.commit()

    result = list_patients(db, condition="measles", page_size=10)
    by_patient = {item["patient_id"]: item for item in result["items"]}
    assert result["total"] == 2
    assert len(by_patient) == 2
    for patient, event_time in zip(patients, event_times):
        deadline = by_patient[str(patient.patient_id)]["deadline"]
        assert deadline["deadline"] == event_time
        assert deadline["disease"] == "measles"
        assert deadline["jurisdiction"] == "TX"
        assert deadline["rule_id"] == "MEASLES-TX"

    refreshed = list_patients(db, condition="measles", page_size=10)
    refreshed_deadlines = {
        item["patient_id"]: item["deadline"]["deadline"]
        for item in refreshed["items"]
    }
    for patient, event_time in zip(patients, event_times):
        assert refreshed_deadlines[str(patient.patient_id)] == event_time
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
    assert "No Texas 2026 reporting deadline rule" in result["items"][0]["deadline_reason"]
    filtered = list_patients(db, condition="measles")
    assert filtered["total"] == 0
    assert filtered["items"] == []
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


def test_measles_condition_timestamp_matching_dob_is_not_a_deadline_event():
    db = _session()
    patient = Patient(
        patient_id=uuid4(), source_patient_id="source-dob-onset",
        date_of_birth=date(1960, 4, 2), state="TX",
        source="test", source_resource="Patient",
    )
    dob_timestamp = datetime(1960, 4, 2, 10, 32, tzinfo=timezone.utc)
    db.add(patient)
    db.flush()
    encounter = Encounter(
        encounter_id=uuid4(), source_encounter_id="later-encounter",
        patient_id=patient.patient_id,
        start_time=datetime(2026, 8, 28, tzinfo=timezone.utc),
        source="test", source_resource="Encounter",
    )
    db.add_all([
        encounter,
        Condition(
            condition_id=uuid4(), source_condition_id="measles-on-dob",
            patient_id=patient.patient_id, encounter_id=encounter.encounter_id,
            condition_display="Measles (disorder)",
            onset_time=dob_timestamp, recorded_time=dob_timestamp,
            source="test", source_resource="Condition",
        ),
    ])
    db.commit()

    result = list_patients(db, condition="measles")
    item = result["items"][0]
    assert result["total"] == 1
    assert item["deadline"]["deadline"] == encounter.start_time.replace(tzinfo=timezone.utc)
    assert item["deadline"]["rule_id"] == "MEASLES-TX"
    db.close()


def test_measles_condition_without_event_uses_last_encounter_fallback():
    db = _session()
    patient = Patient(
        patient_id=uuid4(), source_patient_id="source-no-clinical-event",
        date_of_birth=date(1970, 1, 1), state="TX",
        source="test", source_resource="Patient",
    )
    db.add(patient)
    db.flush()
    encounter_time = datetime(2026, 9, 13, tzinfo=timezone.utc)
    db.add_all([
        Encounter(
            encounter_id=uuid4(), source_encounter_id="recent-encounter",
            patient_id=patient.patient_id,
            start_time=encounter_time,
            source="test", source_resource="Encounter",
        ),
        Condition(
            condition_id=uuid4(), source_condition_id="measles-no-event",
            patient_id=patient.patient_id, condition_display="Measles (disorder)",
            onset_time=None, recorded_time=None,
            source="test", source_resource="Condition",
        ),
    ])
    db.commit()

    result = list_patients(db, condition="measles")
    assert result["total"] == 1
    assert result["items"][0]["deadline"]["deadline"] == encounter_time
    assert result["items"][0]["deadline"]["rule_id"] == "MEASLES-TX"
    db.close()


def test_list_patients_returns_empty_page_for_no_matches():
    db = _session()
    result = list_patients(db, search="not-present")
    assert result["items"] == []
    assert result["total"] == 0
    assert result["pages"] == 0
    db.close()
