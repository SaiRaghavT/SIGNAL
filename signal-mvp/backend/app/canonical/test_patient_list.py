from datetime import date, datetime, timezone
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.canonical.query_service import list_patients
from backend.app.models.condition import Condition
from backend.app.models.encounter import Encounter
from backend.app.models.patient import Patient


def _session() -> Session:
    engine = create_engine("sqlite://")
    Patient.__table__.create(engine)
    Encounter.__table__.create(engine)
    Condition.__table__.create(engine)
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
    assert filtered["items"][0]["severity"] is None
    db.close()


def test_list_patients_returns_empty_page_for_no_matches():
    db = _session()
    result = list_patients(db, search="not-present")
    assert result["items"] == []
    assert result["total"] == 0
    assert result["pages"] == 0
    db.close()
