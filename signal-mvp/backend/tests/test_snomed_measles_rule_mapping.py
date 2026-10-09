from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app.agents.candidate_disposition.schemas import CandidateDispositionRequest
from backend.app.agents.candidate_disposition.service import determine_candidate_disposition
from backend.app.agents.reportability_workflow.schemas import CandidateWorkflowInput
from backend.app.agents.reportability_workflow import service as workflow_service
from backend.app.database import get_db
from backend.app.main import app
from backend.app.rckms.decision_support import evaluate_decision_support
from backend.app.rules.resolver import normalize_disease_name, resolve_rule
from backend.app.demo.synthetic_jordan_reporting import REPORT_FIELD_DEFAULTS
from backend.app.models.case import Case
from backend.app.models.workflow_records import CaseWorkflowRecord


SNOMED_MEASLES = "http://snomed.info/sct|14189004"


def test_snomed_measles_resolves_catalog_rule_and_reconciles_to_report():
    assert normalize_disease_name(SNOMED_MEASLES) == "measles"
    rule = resolve_rule(SNOMED_MEASLES, "TX")
    assert rule["rule_id"] == "MEASLES-TX"
    assert rule["disease"] == "measles"

    decision = evaluate_decision_support(
        candidate_id="candidate-1",
        disease=SNOMED_MEASLES,
        jurisdiction="TX",
        laboratory_evidence=[{"test": "Measles PCR", "result": "positive"}],
        clinical_evidence={"diagnosis": SNOMED_MEASLES},
    )
    reconciled = determine_candidate_disposition(
        CandidateDispositionRequest(
            candidate_id="candidate-1",
            laboratory_decision="POSITIVE",
            rule_decision=decision.decision,
            jurisdiction_status="RESOLVED",
            reportability_decision="PROCEED_TO_RULES",
            human_review_required=decision.human_review_required,
        )
    )

    assert decision.rule_id == "MEASLES-TX"
    assert decision.decision == "REPORT"
    assert reconciled.final_decision == "REPORT"


def test_candidate_pipeline_normalizes_persisted_snomed_diagnosis(monkeypatch):
    patient_id = uuid4()
    monkeypatch.setattr(
        workflow_service,
        "get_patient_context",
        lambda **_kwargs: {
            "patient": {
                "patient_id": str(patient_id),
                "source_patient_id": "patient-1",
                "first_name": "Taylor",
                "last_name": "Example",
                "date_of_birth": "1980-01-01",
                "sex": "Female",
                "address": {"state": "TX", "county": "Travis"},
            },
            "conditions": [],
            "encounters": [],
            "lab_results": [],
            "clinical_documents": [],
        },
    )
    monkeypatch.setattr(
        workflow_service,
        "resolve_jurisdiction",
        lambda _request: SimpleNamespace(
            jurisdiction="TX", status="RESOLVED", reasons=[]
        ),
    )
    monkeypatch.setattr(
        workflow_service,
        "populate_report_fields",
        lambda _data: SimpleNamespace(
            fields={},
            populated_fields=[],
            required_missing_fields=[],
            missing_fields=[],
            sources={},
            confidence={},
            warnings=[],
        ),
    )
    monkeypatch.setattr(
        workflow_service,
        "assemble_case",
        lambda data, _db, existing_case_id=None: SimpleNamespace(
            case_id=existing_case_id or "assembled-case",
            status=data.final_decision,
            warnings=[],
            disease=data.disease,
            jurisdiction=data.jurisdiction,
            jurisdiction_status=data.jurisdiction_status,
            reportability_decision=data.reportability_decision,
            reportability_evidence_status=data.reportability_evidence_status,
            rule_id=data.rule_id,
        ),
    )
    monkeypatch.setattr(
        workflow_service,
        "build_ecr",
        lambda case: SimpleNamespace(ecr_id="ecr-1", status=case.status, rule_id=case.rule_id, warnings=[]),
    )
    monkeypatch.setattr(
        workflow_service,
        "validate_ecr",
        lambda *_args: SimpleNamespace(valid=True, errors=[], warnings=[], completion_required=[]),
    )
    monkeypatch.setattr(
        workflow_service,
        "submit_ecr",
        lambda *_args: SimpleNamespace(status="READY", submission_id=None, destination=None, errors=[], warnings=[]),
    )

    result = workflow_service.process_candidate(
        CandidateWorkflowInput(
            candidate_id=str(patient_id),
            patient_id=patient_id,
            disease=SNOMED_MEASLES,
            clinical_evidence={"diagnosis": SNOMED_MEASLES},
            laboratory_evidence=[{"test": "Measles PCR", "result": "positive"}],
        ),
        db=object(),
    )

    assert result["jurisdiction"]["status"] == "RESOLVED"
    assert result["workflow_status"] == "REPORT"
    assert result["rule_evaluation"]["rule_id"] == "MEASLES-TX"
    assert result["case"]["status"] == "REPORT"


class FakeQuery:
    def __init__(self, session, model):
        self.session = session
        self.model = model
        self.rows = list(session.records.get(model, []))

    def filter(self, *expressions):
        return self

    def order_by(self, *expressions):
        return self

    def first(self):
        if self.model is Case:
            return self.session.case
        return self.rows[-1] if self.rows else None

    def all(self):
        return self.rows


class FakeSession:
    def __init__(self, case):
        self.case = case
        self.records = {CaseWorkflowRecord: []}

    def query(self, model):
        return FakeQuery(self, model)

    def add(self, record):
        self.records.setdefault(type(record), []).append(record)

    def commit(self):
        pass

    def refresh(self, record):
        record.record_id = record.record_id or str(uuid4())
        now = datetime.now(timezone.utc)
        record.created_at = record.created_at or now
        record.updated_at = record.updated_at or now


def test_review_api_approves_corrected_report_case_after_validation(monkeypatch):
    case_id = uuid4()
    case = SimpleNamespace(
        case_id=case_id,
        candidate_id="candidate-1",
        status="REPORT",
        disease="measles",
        jurisdiction="TX",
        jurisdiction_status="RESOLVED",
        reportability_decision="REPORT",
        reportability_evidence_status="LAB_POSITIVE",
        final_decision="REPORT",
        rule_id="MEASLES-TX",
        patient={"first_name": "Jordan", "last_name": "Rivera", "date_of_birth": "2018-04-12"},
        facility={"name": "SIGNAL Demonstration Clinic"},
        provider={"name": "Taylor Morgan, MD", "phone": "512-555-0199", "address": "200 Sample Street"},
        clinical_evidence={"diagnosis": "Measles"},
        laboratory_evidence=[{"test": "Measles PCR", "result": "positive"}],
        ai_evidence={},
        report_fields=dict(REPORT_FIELD_DEFAULTS),
        warnings=[],
        submission_mode="IMMEDIATE",
        deadline=datetime(2026, 10, 8, tzinfo=timezone.utc),
        severity="HIGH",
    )
    session = FakeSession(case)
    monkeypatch.setattr("backend.app.case.workflow_api.audit.record_event", lambda *args, **kwargs: None)

    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        response = client.post(
            f"/api/cases/{case_id}/review",
            json={
                "reviewer_id": "clinical-staff@example.org",
                "reviewer_role": "REPORTING_STAFF",
                "decision": "APPROVE",
            },
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 201
    assert response.json()["status"] == "APPROVE"
    assert case.final_decision == "REPORT"
    assert case.rule_id == "MEASLES-TX"
