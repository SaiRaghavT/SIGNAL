from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.candidate.schemas import CandidateResponse
from app.candidate.service import (
    _without_persisted_scores,
    candidate_to_response,
    persist_detection_candidates,
)
from backend.app.models.candidate import Candidate


class _Query:
    def __init__(self, result=None):
        self.result = result

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return self.result


class _FakeDB:
    def __init__(self, query_result=None):
        self.query_result = query_result
        self.added = []

    def query(self, _model):
        return _Query(self.query_result)

    def add(self, value):
        self.added.append(value)

    def flush(self):
        for value in self.added:
            if isinstance(value, Candidate) and not value.candidate_id:
                value.candidate_id = "candidate-001"

    def commit(self):
        pass

    def refresh(self, _value):
        pass


def test_persistence_stores_signals_without_persisting_scores(monkeypatch):
    from app.candidate import service

    monkeypatch.setattr(service.AuditLedgerService, "record_event", lambda *_args, **_kwargs: None)
    db = _FakeDB()
    signal = {
        "trigger_id": "configured-condition",
        "trigger_type": "CONDITION_CODE",
        "evidence": {"source_type": "Condition", "source_id": "condition-001"},
        "confidence": 0.99,
    }
    candidate_data = {
        "disease_id": "measles",
        "trigger_types": ["CONDITION_CODE"],
        "signals": [signal],
        "evidence": [signal["evidence"]],
        "confidence": 0.60,
        "evidence_strength": 1.0,
        "evidence_strength_method": "legacy_unweighted",
        "evidence_strength_components": [{"factor": "structured_trigger", "points": 1.0}],
        "primary_trigger": {"type": "structured", "source_id": "condition-001"},
    }

    rows = persist_detection_candidates(db, {"patient_id": "patient-001", "candidates": [candidate_data]})

    assert not hasattr(rows[0], "evidence_strength")
    assert not hasattr(rows[0], "confidence")
    assert "confidence" not in rows[0].signals[0]


def test_candidate_table_has_no_confidence_or_evidence_strength_columns():
    assert "confidence" not in Candidate.__table__.columns
    assert "evidence_strength" not in Candidate.__table__.columns


def test_audit_payload_omits_calculated_score_fields():
    clean = _without_persisted_scores({
        "evidence_strength": 100,
        "evidence_strength_components": [{"points": 100}],
        "confidence": 1,
        "signals": [{"confidence": 0.99, "evidence_strength": 90, "trigger_type": "LAB_RESULT"}],
    })
    assert "evidence_strength" not in clean
    assert "confidence" not in clean
    assert clean["signals"] == [{"trigger_type": "LAB_RESULT"}]


def test_refresh_does_not_add_score_attributes_to_existing_candidate(monkeypatch):
    from types import SimpleNamespace
    from app.candidate import service

    monkeypatch.setattr(service.AuditLedgerService, "record_event", lambda *_args, **_kwargs: None)
    existing = SimpleNamespace(candidate_id="candidate-001")
    db = _FakeDB(query_result=existing)
    signal = {
        "trigger_id": "condition-trigger", "trigger_type": "CONDITION_CODE",
        "evidence": {"source_type": "Condition", "source_id": "condition-001"},
    }

    rows = persist_detection_candidates(db, {
        "patient_id": "patient-001",
        "candidates": [{
            "disease_id": "measles", "trigger_types": ["CONDITION_CODE"],
            "signals": [signal], "evidence": [signal["evidence"]],
        }],
    })

    assert not hasattr(rows[0], "confidence")
    assert not hasattr(rows[0], "evidence_strength")


def test_api_serializes_evidence_strength_without_exposing_legacy_confidence():
    patient = type("PatientRow", (), {
        "patient_id": "patient-001", "first_name": "Test", "last_name": "Patient",
        "date_of_birth": None, "sex": None,
    })()
    candidate = type("CandidateRow", (), {
        "candidate_id": "candidate-001", "patient_id": "patient-001", "disease_id": "measles",
        "jurisdiction": "TX", "evidence": [],
        "signals": [{"trigger_type": "CONDITION_CODE", "trigger_id": "condition", "evidence": {"source_id": "condition-1"}}],
        "confidence": 0.25, "status": "POTENTIAL", "case_id": None,
        "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc),
    })()

    response = candidate_to_response(_FakeDB(patient), candidate)

    assert response.evidence_strength == 60.0
    assert response.evidence_strength_method == "weighted_rule_based_v2"
    assert response.confidence is None
    assert response.confidence_method == "unavailable"
    assert response.primary_trigger["source_id"] == "condition-1"


def test_api_rejects_scores_outside_zero_to_one_hundred():
    values = {
        "candidate_id": "candidate-001", "patient_id": "patient-001", "patient": {},
        "disease": "measles", "status": "POTENTIAL",
        "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc),
        "evidence_strength": 100.1,
    }
    with pytest.raises(ValidationError):
        CandidateResponse.model_validate(values)
