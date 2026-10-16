from __future__ import annotations

import threading
import time
import json
import sys
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi import HTTPException

from backend.app.agents.nlp_evidence import cache
from backend.app.agents.nlp_evidence import service as evidence_service
from backend.app.detection import run_lock


def _document(source_id: str, text: str = "Fever is documented.") -> dict[str, str]:
    return {
        "document_id": source_id,
        "patient_id": "patient-test",
        "document_type": "ClinicalDocument",
        "title": "Note",
        "text": text,
    }


def test_evidence_cache_hits_and_invalidates_changed_content_or_configuration():
    cache.clear_cache()
    document = _document("source-1")
    first_key = evidence_service._cache_key_for_document(document, "openrouter", "model-a")
    cache.store_cached(first_key, [{"evidence_type": "symptom", "concept": "fever"}])

    assert cache.get_cached(first_key) == [{"evidence_type": "symptom", "concept": "fever"}]
    assert cache.get_cached(evidence_service._cache_key_for_document(document, "openrouter", "model-b")) is None
    assert cache.get_cached(evidence_service._cache_key_for_document(_document("source-1", "Edited."), "openrouter", "model-a")) is None

    edited = _document("source-1", "Edited.")
    cache.prune_patient_sources(
        "patient-test",
        {cache.source_identity(edited): cache.source_content_hash(edited)},
    )
    assert cache.cache_size() == 0


def test_incomplete_evidence_response_is_not_cached():
    cache.clear_cache()
    document = _document("source-partial")
    evidence_service._cache_complete_response(
        document,
        [{"evidence_type": "symptom"}, {"bad": "item"}],
        [{"evidence_type": "symptom"}],
        provider="openrouter",
        model="model-a",
    )
    assert cache.cache_size() == 0

    # An empty, schema-valid evidence array is a complete answer and is cached.
    evidence_service._cache_complete_response(
        document, [], [], provider="openrouter", model="model-a",
    )
    assert cache.cache_size() == 1


def test_cache_key_changes_when_prompt_or_provider_credential_changes(monkeypatch):
    document = _document("source-config")
    original = evidence_service._cache_key_for_document(document, "openrouter", "model-a")
    monkeypatch.setattr(evidence_service.settings, "openrouter_api_key", "different-offline-key")
    changed_key = evidence_service._cache_key_for_document(document, "openrouter", "model-a")
    monkeypatch.setattr(evidence_service.settings, "openrouter_api_key", None)
    monkeypatch.setattr(evidence_service, "NLP_EVIDENCE_SYSTEM_PROMPT", "changed prompt")
    changed_prompt = evidence_service._cache_key_for_document(document, "openrouter", "model-a")

    assert original != changed_key
    assert original != changed_prompt


def test_successful_provider_response_is_cached_and_reused_without_network(monkeypatch):
    cache.clear_cache()
    monkeypatch.setattr(evidence_service.settings, "llm_provider", "openrouter")
    monkeypatch.setattr(evidence_service.settings, "openrouter_api_key", "offline-test-key")
    monkeypatch.setattr(evidence_service.settings, "detection_ai_max_concurrency", 1, raising=False)
    calls = []
    payload = {
        "evidence": [{
            "evidence_type": "symptom",
            "concept": "fever",
            "evidence_text": "Fever is documented.",
            "assertion": "present",
            "temporality": "current",
            "confidence": 0.8,
        }]
    }

    class FakeClient:
        def __init__(self, **_kwargs):
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

        def create(self, **_kwargs):
            calls.append(1)
            return SimpleNamespace(choices=[SimpleNamespace(
                message=SimpleNamespace(content=json.dumps(payload))
            )])

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeClient))
    document = _document("source-cached")
    first = evidence_service.extract_evidence([document], run_id="offline-cache-1")
    second = evidence_service.extract_evidence([document], run_id="offline-cache-2")

    assert len(calls) == 1
    assert first == second
    assert first[0]["document_id"] == "source-cached"
    assert first[0]["source_title"] == "Note"


def test_deleted_source_entries_are_pruned():
    cache.clear_cache()
    first = _document("source-one")
    second = _document("source-two")
    for document in (first, second):
        key = evidence_service._cache_key_for_document(document, "openrouter", "model-a")
        cache.store_cached(key, [])

    cache.prune_patient_sources(
        "patient-test",
        {cache.source_identity(first): cache.source_content_hash(first)},
    )
    assert cache.cache_size() == 1


def test_extraction_uses_configured_concurrency_and_preserves_source_order(monkeypatch):
    cache.clear_cache()
    monkeypatch.setattr(evidence_service.settings, "detection_ai_max_concurrency", 2, raising=False)
    active = 0
    max_active = 0
    guard = threading.Lock()

    def fake_worker(document):
        nonlocal active, max_active
        with guard:
            active += 1
            max_active = max(max_active, active)
        time.sleep(0.02)
        result = [{"document_id": document["document_id"]}]
        with guard:
            active -= 1
        return result

    docs = [_document(f"source-{index}") for index in range(6)]
    result = evidence_service._run_provider_documents_concurrently(
        docs,
        run_id="offline-run",
        provider="openrouter",
        model="offline-model",
        worker=fake_worker,
    )

    assert max_active == 2
    assert result is not None
    assert [item["document_id"] for item in result] == [doc["document_id"] for doc in docs]


def test_provider_failure_does_not_return_partial_evidence(monkeypatch):
    cache.clear_cache()
    monkeypatch.setattr(evidence_service.settings, "llm_provider", "openrouter")
    monkeypatch.setattr(evidence_service.settings, "openrouter_api_key", "offline-test-key")
    monkeypatch.setattr(evidence_service.settings, "gemini_api_key", None)
    monkeypatch.setattr(evidence_service.settings, "groq_api_key", None)
    monkeypatch.setattr(evidence_service.settings, "groq_run_detection_api_key", None, raising=False)
    monkeypatch.setattr(evidence_service.settings, "detection_ai_max_concurrency", 2, raising=False)

    def fake_openrouter(documents, *, run_id):
        results = []
        for document in documents:
            if document["document_id"] == "source-fail":
                raise ValueError("provider response omitted required evidence")
            item = {
                "evidence_type": "symptom",
                "concept": "fever",
                "evidence_text": "Fever is documented.",
                "assertion": "present",
                "temporality": "current",
                "confidence": 0.8,
            }
            normalized = evidence_service._normalize_evidence([item], document)
            evidence_service._cache_complete_response(
                document, [item], normalized, provider="openrouter", model="openai/gpt-oss-20b",
            )
            results.extend(normalized)
        return results

    monkeypatch.setattr(evidence_service, "_extract_with_openrouter", fake_openrouter)
    with pytest.raises(evidence_service.DocumentAIUnavailableError):
        evidence_service.extract_evidence(
            [_document("source-ok"), _document("source-fail")],
            run_id="offline-failure",
        )
    assert cache.get_cached(evidence_service._cache_key_for_document(
        _document("source-ok"), "openrouter", "openai/gpt-oss-20b",
    )) is not None
    assert cache.get_cached(evidence_service._cache_key_for_document(
        _document("source-fail"), "openrouter", "openai/gpt-oss-20b",
    )) is None


def test_groq_rate_limit_wait_is_bounded_and_retried_offline(monkeypatch):
    class RateLimitError(Exception):
        status_code = 429

    class Completions:
        calls = 0

        def create(self, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                raise RateLimitError("try again in 1.5s")
            return "response"

    completions = Completions()
    waits = []
    monkeypatch.setattr(evidence_service.time, "sleep", waits.append)
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))

    response = evidence_service._create_groq_completion(
        client,
        {},
        run_id="offline-retry",
        source_id="hashed-source-id",
        model="offline-model",
    )

    assert response == "response"
    assert completions.calls == 2
    assert waits == [1.5]


def test_primary_provider_failure_uses_configured_fallback(monkeypatch):
    cache.clear_cache()
    monkeypatch.setattr(evidence_service.settings, "llm_provider", "openrouter")
    monkeypatch.setattr(evidence_service.settings, "openrouter_api_key", "offline-test-key")
    monkeypatch.setattr(evidence_service.settings, "gemini_api_key", "offline-gemini-key")
    monkeypatch.setattr(evidence_service.settings, "groq_api_key", None)
    monkeypatch.setattr(evidence_service.settings, "groq_run_detection_api_key", None, raising=False)
    monkeypatch.setattr(evidence_service.settings, "detection_ai_max_concurrency", 1, raising=False)

    def fail_primary(*_args, **_kwargs):
        raise TimeoutError("offline provider failure")

    monkeypatch.setattr(evidence_service, "_extract_with_openrouter", fail_primary)
    monkeypatch.setattr(
        evidence_service,
        "_extract_with_gemini",
        lambda documents, **_: [
            {"document_id": document["document_id"], "source_type": "fallback"}
            for document in documents
        ],
    )

    result = evidence_service.extract_evidence(
        [_document("source-fallback-1"), _document("source-fallback-2")],
        run_id="offline-fallback",
    )
    assert result == [
        {"document_id": "source-fallback-1", "source_type": "fallback"},
        {"document_id": "source-fallback-2", "source_type": "fallback"},
    ]


class _Scalar:
    def __init__(self, value):
        self.value = value

    def scalar(self):
        return self.value


class _FakeConnection:
    def __init__(self, engine):
        self.engine = engine
        self.closed = False
        self.invalidated = False

    def execute(self, statement, params):
        query = str(statement)
        key = params["lock_key"]
        if "pg_try_advisory_lock" in query:
            with self.engine.guard:
                if key in self.engine.held:
                    return _Scalar(False)
                self.engine.held.add(key)
                return _Scalar(True)
        if "pg_advisory_unlock" in query:
            with self.engine.guard:
                self.engine.held.discard(key)
            return _Scalar(True)
        raise AssertionError("unexpected SQL")

    def commit(self):
        pass

    def close(self):
        self.closed = True

    def invalidate(self):
        self.invalidated = True
        self.engine.held.clear()


class _FakeEngine:
    def __init__(self):
        self.held = set()
        self.connections = []
        self.guard = threading.Lock()

    def connect(self):
        connection = _FakeConnection(self)
        self.connections.append(connection)
        return connection


def test_postgres_advisory_lease_rejects_second_request_and_releases_for_retry():
    engine = _FakeEngine()
    patient_id = UUID("bb06202c-79bc-58c9-a8d6-be0000000000")
    lease = run_lock.try_acquire_patient_detection_lease(engine, patient_id)
    assert lease is not None
    assert run_lock.try_acquire_patient_detection_lease(engine, patient_id) is None
    lease.release()
    assert engine.connections[0].closed
    retry_lease = run_lock.try_acquire_patient_detection_lease(engine, patient_id)
    assert retry_lease is not None
    retry_lease.release()


def test_simultaneous_same_patient_acquisitions_allow_only_one_worker():
    engine = _FakeEngine()
    patient_id = UUID("bb06202c-79bc-58c9-a8d6-be0000000000")
    barrier = threading.Barrier(3)
    results = []

    def acquire():
        barrier.wait()
        results.append(run_lock.try_acquire_patient_detection_lease(engine, patient_id))

    workers = [threading.Thread(target=acquire) for _ in range(2)]
    for worker in workers:
        worker.start()
    barrier.wait()
    for worker in workers:
        worker.join()

    assert sum(lease is not None for lease in results) == 1
    next(lease for lease in results if lease is not None).release()


def test_advisory_lease_invalidates_connection_when_unlock_fails():
    engine = _FakeEngine()
    lease = run_lock.try_acquire_patient_detection_lease(engine, "patient-test")
    connection = engine.connections[0]

    def fail_unlock(_statement, _params):
        raise RuntimeError("offline database failure")

    connection.execute = fail_unlock
    with pytest.raises(RuntimeError):
        lease.release()
    assert connection.invalidated
    assert connection.closed


@pytest.mark.parametrize("failure", [RuntimeError, TimeoutError, KeyboardInterrupt])
def test_detection_route_releases_lease_after_pipeline_exit(monkeypatch, failure):
    from backend.app.detection import api

    class Lease:
        released = False

        def release(self):
            self.released = True

    lease = Lease()
    monkeypatch.setattr(api, "try_acquire_patient_detection_lease", lambda *_: lease)
    monkeypatch.setattr(api, "get_patient_context", lambda **_: (_ for _ in ()).throw(failure("offline")))

    with pytest.raises(failure):
        api.detect_patient_candidates(
            api.CandidateDetectionRequest(patient_id=UUID("bb06202c-79bc-58c9-a8d6-be0000000000")),
            db=object(),
        )
    assert lease.released


def test_detection_route_returns_conflict_when_patient_run_is_active(monkeypatch):
    from backend.app.detection import api

    monkeypatch.setattr(api, "try_acquire_patient_detection_lease", lambda *_: None)
    with pytest.raises(HTTPException) as error:
        api.detect_patient_candidates(
            api.CandidateDetectionRequest(patient_id=UUID("bb06202c-79bc-58c9-a8d6-be0000000000")),
            db=object(),
        )
    assert error.value.status_code == 409


def test_detection_route_preserves_response_and_audit_contract_without_inference(monkeypatch):
    from backend.app.detection import api

    class Lease:
        released = False

        def release(self):
            self.released = True

    lease = Lease()
    monkeypatch.setattr(api, "try_acquire_patient_detection_lease", lambda *_: lease)
    monkeypatch.setattr(api, "get_patient_context", lambda **_: {
        "patient": {"patient_id": "patient-test", "source_patient_id": "non-demo"},
        "conditions": [], "observations": [], "lab_results": [],
        "clinical_documents": [], "encounters": [],
    })
    monkeypatch.setattr(api, "detect_candidates", lambda *_args, **_kwargs: {
        "patient_id": "patient-test", "signal_count": 1, "candidate_count": 1,
        "signals": [], "candidates": [{"disease_id": "example", "signals": [], "evidence": []}],
    })
    monkeypatch.setattr(api, "persist_detection_candidates", lambda *_args, **_kwargs: [
        SimpleNamespace(candidate_id="candidate-1", case_id="case-1", status="POTENTIAL")
    ])
    audit_events = []

    class AuditService:
        def record_event(self, event, _db):
            audit_events.append(event)
            return SimpleNamespace(audit_id="audit-1")

    monkeypatch.setattr(api, "AuditLedgerService", AuditService)
    response = api.detect_patient_candidates(
        api.CandidateDetectionRequest(patient_id=UUID("bb06202c-79bc-58c9-a8d6-be0000000000")),
        db=object(),
    )

    assert response["document_evidence_status"] == "no_document_text"
    assert response["detection_run"]["status"] == "COMPLETED"
    assert response["detection_run"]["audit_id"] == "audit-1"
    assert response["candidates"][0]["candidate_id"] == "candidate-1"
    assert response["candidates"][0]["case_id"] == "case-1"
    assert response["diagnostics"]["run_id"]
    assert audit_events[0].event_type == "DETECTION_COMPLETED"
    assert lease.released
