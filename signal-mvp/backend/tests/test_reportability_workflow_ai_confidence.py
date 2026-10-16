from types import SimpleNamespace
from uuid import uuid4

from backend.app.agents.reportability_workflow import router
from backend.app.agents.reportability_workflow.schemas import CandidateProcessRequest
from backend.app.models.candidate import Candidate


def test_candidate_evidence_strength_is_not_passed_as_ai_confidence(monkeypatch):
    candidate = SimpleNamespace(
        candidate_id="candidate-1",
        patient_id=str(uuid4()),
        disease_id="measles",
        confidence=0.85,
        evidence=[],
        signals=[],
        status="POTENTIAL",
        case_id=None,
        jurisdiction=None,
    )

    class Query:
        def filter(self, *_args):
            return self

        def first(self):
            return candidate

    class DB:
        def query(self, model):
            assert model is Candidate
            return Query()

        def commit(self):
            pass

    captured = {}

    def process_candidate(request, _db):
        captured["request"] = request
        return {
            "case": {"case_id": "case-1"},
            "jurisdiction": {"value": None},
            "workflow_status": "REVIEW",
        }

    monkeypatch.setattr(router, "process_candidate", process_candidate)
    monkeypatch.setattr(router, "AuditLedgerService", lambda: SimpleNamespace(record_event=lambda *_args: None))

    router.process_candidate_endpoint(CandidateProcessRequest(candidate_id="candidate-1"), DB())

    request = captured["request"]
    assert request.ai_evidence == {}
    assert request.laboratory_evidence == []
