from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app.database import get_db
from backend.app.main import app
from backend.app.models.case import Case
from backend.app.case.reporting_service import update_case_report
from backend.app.case.schemas import CaseReportUpdateRequest
from backend.app.case.report_fields import missing_report_fields


class FakeQuery:
    def __init__(self, session, model):
        self.session = session
        self.model = model

    def filter(self, *args):
        return self

    def order_by(self, *args):
        return self

    def all(self):
        return []

    def first(self):
        return self.session.case if self.model is Case else None


class FakeSession:
    def __init__(self, case):
        self.case = case

    def query(self, model):
        return FakeQuery(self, model)

    def commit(self):
        pass

    def refresh(self, instance):
        pass


def test_reporting_form_values_persist_and_round_trip_through_case_api(monkeypatch):
    now = datetime.now(timezone.utc)
    case_id = uuid4()
    case = SimpleNamespace(
        case_id=case_id,
        candidate_id="candidate-1",
        patient={"patient_id": "patient-1", "date_of_birth": "2000-01-01"},
        facility={"name": "Clinic"},
        provider={"name": "Provider", "phone": "555-0100", "address": "1 Main St"},
        disease="measles",
        clinical_evidence={"diagnosis": "measles"},
        laboratory_evidence=[{"test_name": "PCR", "result": "positive"}],
        ai_evidence={},
        report_fields={},
        jurisdiction="TX",
        jurisdiction_status="RESOLVED",
        reportability_decision="PROCEED_TO_RULES",
        reportability_evidence_status="CONFIRMED",
        status="NEEDS_REVIEW",
        final_decision="REPORT",
        rule_id="rule-1",
        deadline=None,
        severity="HIGH",
        warnings=[],
        created_at=now,
        updated_at=now,
    )
    session = FakeSession(case)

    monkeypatch.setattr(
        "backend.app.case.reporting_service.AuditLedgerService.record_event",
        lambda *args, **kwargs: None,
    )

    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app)
        values = {
            "reporting.investigated_by": "Clinical Staff",
            "reporting.investigating_agency": "County Health",
            "reporting.investigating_agency_email": "staff@example.org",
            "reporting.investigating_agency_phone": "555-0123",
            "reporting.investigation_start_date": "2026-10-01",
        }
        saved = client.patch(
            f"/api/cases/{case_id}/report-fields",
            json={"report_fields": values},
        )
        assert saved.status_code == 200
        assert saved.json()["report_fields"] == values

        reread = client.get(f"/api/cases/{case_id}")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert reread.status_code == 200
    assert {key: reread.json()["report_fields"][key] for key in values} == values


def test_synthetic_jordan_defaults_fill_and_persist_missing_reporting_details(monkeypatch):
    now = datetime.now(timezone.utc)
    case_id = uuid4()
    case = SimpleNamespace(
        case_id=case_id,
        candidate_id="synthetic-jordan-candidate",
        patient={
            "patient_id": "bb06202b-79bc-58c9-a8d6-be96e0775fdb",
            "source_patient_id": "SIGNAL-DEMO-MEASLES-001",
            "provenance": {"source": "SIGNAL_DEMO"},
            "first_name": "Jordan",
            "last_name": "Rivera",
            "date_of_birth": "2018-04-12",
            "sex": "Female",
            "address": "100 Demo Avenue",
            "city": "Austin",
            "county": "Travis",
            "state": "TX",
            "postal_code": "78701",
        },
        facility={"facility_id": "SIGNAL-DEMO-CLINIC", "source": "SIGNAL_DEMO"},
        provider={"status": "MISSING", "missing_fields": ["name", "phone", "address"]},
        disease="measles",
        clinical_evidence={},
        laboratory_evidence=[{"test": "Measles PCR", "result": "POSITIVE"}],
        ai_evidence={},
        report_fields={"reporting.investigated_by": "Clinical Staff"},
        jurisdiction="TX",
        jurisdiction_status="RESOLVED",
        reportability_decision="REPORT",
        reportability_evidence_status="LAB_POSITIVE",
        status="NEEDS_REVIEW",
        final_decision="NEEDS_REVIEW",
        rule_id="NO_RULE_AVAILABLE",
        deadline=None,
        severity="HIGH",
        warnings=[],
        created_at=now,
        updated_at=now,
    )
    session = FakeSession(case)
    monkeypatch.setattr(
        "backend.app.case.reporting_service.AuditLedgerService.record_event",
        lambda *args, **kwargs: None,
    )

    result = update_case_report(
        session,
        case_id,
        CaseReportUpdateRequest(report_fields={}),
    )

    assert result.required_missing_fields == []
    assert case.patient["country_of_residence"] == "United States"
    assert case.patient["race"] == "Unknown"
    assert case.provider["name"] == "Taylor Morgan, MD"
    assert case.facility["name"] == "SIGNAL Demonstration Clinic"
    assert case.report_fields["clinical.hospitalized"] == "No"
    assert case.report_fields["laboratory.igm"] == "Not documented"
    assert case.report_fields["reporting.investigated_by"] == "Clinical Staff"
    assert case.reportability_decision == "REPORT"
    assert case.final_decision == "REPORT"
    assert case.rule_id == "TX-MEASLES-IMMEDIATE"
    assert any("not a real patient record" in warning for warning in case.warnings)


def test_synthetic_jordan_defaults_do_not_apply_to_other_cases():
    from backend.app.demo.synthetic_jordan_reporting import apply_synthetic_jordan_reporting_defaults

    case = SimpleNamespace(
        patient={"patient_id": "other-patient", "provenance": {"source": "SIGNAL_DEMO"}},
        facility={"facility_id": "SIGNAL-DEMO-CLINIC"},
        provider={},
        clinical_evidence={},
        report_fields={},
        warnings=[],
    )

    assert apply_synthetic_jordan_reporting_defaults(case) == []
    assert case.report_fields == {}
