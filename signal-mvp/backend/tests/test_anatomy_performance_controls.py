import json
import heapq
import random
import threading
import time
from uuid import UUID

import pytest

from backend.app.anatomy import llm as anatomy_llm
from backend.app.anatomy.markers import _nearest_surface_points_by_xy
from backend.app.config.settings import settings


def _document(source_id="doc-1", text="Rash on face."):
    return {
        "document_id": source_id,
        "title": "Synthetic note",
        "extracted_text": text,
    }


def _empty_response(prompt_json, provider, model):
    prompt = json.loads(prompt_json)
    return json.dumps({"findings": []})


def test_nearest_surface_lookup_matches_full_distance_sort():
    randomizer = random.Random(7)
    points = [(randomizer.uniform(-1, 1), randomizer.uniform(-1, 1), float(index)) for index in range(2500)]
    sorted_points = sorted(
        ((point[0], index, point) for index, point in enumerate(points)),
        key=lambda item: (item[0], item[1]),
    )
    actual = _nearest_surface_points_by_xy(
        sorted_points, [item[0] for item in sorted_points], 0.15, -0.2, 24
    )
    expected = heapq.nsmallest(
        24, enumerate(points),
        key=lambda indexed: (indexed[1][0] - 0.15) ** 2 + (indexed[1][1] + 0.2) ** 2,
    )

    assert set(actual) == {point for _index, point in expected}


@pytest.fixture(autouse=True)
def _clear_anatomy_state():
    with anatomy_llm._ANATOMY_RESPONSE_CACHE_LOCK:
        anatomy_llm._ANATOMY_RESPONSE_CACHE.clear()
    with anatomy_llm._PROVIDER_COOLDOWNS_LOCK:
        anatomy_llm._PROVIDER_COOLDOWNS.clear()
    yield
    with anatomy_llm._ANATOMY_RESPONSE_CACHE_LOCK:
        anatomy_llm._ANATOMY_RESPONSE_CACHE.clear()


def test_anatomy_cache_reuses_unchanged_response_and_invalidates_content(monkeypatch):
    calls = []
    monkeypatch.setattr(anatomy_llm, "_configured_providers", lambda: [("groq", "test-model")])
    monkeypatch.setattr(anatomy_llm, "_request_uncached", lambda *args: calls.append(args) or _empty_response(*args))

    anatomy_llm.derive_anatomy_findings_with_llm([_document()], patient_id="synthetic-patient")
    anatomy_llm.derive_anatomy_findings_with_llm([_document()], patient_id="synthetic-patient")
    assert len(calls) == 1

    anatomy_llm.derive_anatomy_findings_with_llm(
        [_document(text="Rash on both hands.")], patient_id="synthetic-patient"
    )
    assert len(calls) == 2


def test_refresh_bypasses_cache_without_clearing_other_entries(monkeypatch):
    calls = []
    monkeypatch.setattr(anatomy_llm, "_configured_providers", lambda: [("groq", "test-model")])
    monkeypatch.setattr(anatomy_llm, "_request_uncached", lambda *args: calls.append(args) or _empty_response(*args))

    anatomy_llm.derive_anatomy_findings_with_llm([_document("a")], patient_id="p")
    anatomy_llm.derive_anatomy_findings_with_llm([_document("a")], patient_id="p", force_refresh=True)
    anatomy_llm.derive_anatomy_findings_with_llm([_document("b")], patient_id="p")
    anatomy_llm.derive_anatomy_findings_with_llm([_document("a")], patient_id="p")
    assert len(calls) == 3


def test_anatomy_cache_invalidates_model_prompt_and_provider_credential(monkeypatch):
    calls = []
    current = {"model": "model-a", "credential": "credential-a"}
    monkeypatch.setattr(
        anatomy_llm, "_configured_providers",
        lambda: [("groq", current["model"])],
    )
    monkeypatch.setattr(anatomy_llm, "_anatomy_groq_api_key", lambda: current["credential"])
    monkeypatch.setattr(anatomy_llm, "_request_uncached", lambda *args: calls.append(args) or _empty_response(*args))
    document = [_document()]

    anatomy_llm.derive_anatomy_findings_with_llm(document, patient_id="p")
    anatomy_llm.derive_anatomy_findings_with_llm(document, patient_id="p")
    current["model"] = "model-b"
    anatomy_llm.derive_anatomy_findings_with_llm(document, patient_id="p")
    current["credential"] = "credential-b"
    anatomy_llm.derive_anatomy_findings_with_llm(document, patient_id="p")
    monkeypatch.setattr(anatomy_llm, "ANATOMY_SYSTEM_PROMPT", anatomy_llm.ANATOMY_SYSTEM_PROMPT + "\nVersion change.")
    anatomy_llm.derive_anatomy_findings_with_llm(document, patient_id="p")

    assert len(calls) == 4


def test_anatomy_batches_use_bounded_concurrency(monkeypatch):
    active = 0
    peak = 0
    guard = threading.Lock()

    def request(*args):
        nonlocal active, peak
        with guard:
            active += 1
            peak = max(peak, active)
        time.sleep(0.04)
        with guard:
            active -= 1
        return _empty_response(*args)

    monkeypatch.setattr(settings, "anatomy_ai_max_concurrency", 2)
    monkeypatch.setattr(anatomy_llm, "_configured_providers", lambda: [("groq", "test-model")])
    monkeypatch.setattr(anatomy_llm, "_request_uncached", request)
    documents = [_document(f"doc-{index}") for index in range(10)]

    anatomy_llm.derive_anatomy_findings_with_llm(documents, patient_id="synthetic-patient")

    assert peak == 2


def test_timing_logs_exclude_source_identifiers_and_note_text(monkeypatch, caplog):
    monkeypatch.setattr(anatomy_llm, "_configured_providers", lambda: [("groq", "test-model")])
    monkeypatch.setattr(anatomy_llm, "_request_uncached", lambda *args: _empty_response(*args))
    secret_source_id = "synthetic-source-id-private"
    secret_note = "Synthetic private note wording that must not appear in logs."

    with caplog.at_level("INFO", logger="signal.ai_detection"):
        anatomy_llm.derive_anatomy_findings_with_llm(
            [_document(secret_source_id, secret_note)], patient_id="synthetic-patient"
        )

    assert secret_source_id not in caplog.text
    assert secret_note not in caplog.text


def test_failed_or_invalid_provider_response_is_not_cached(monkeypatch):
    calls = []

    def invalid(*args):
        calls.append(args)
        return '{"findings": ['

    monkeypatch.setattr(anatomy_llm, "_configured_providers", lambda: [("groq", "test-model")])
    monkeypatch.setattr(anatomy_llm, "_request_uncached", invalid)
    for _ in range(2):
        with pytest.raises(RuntimeError, match="Configured anatomy LLM providers failed"):
            anatomy_llm.derive_anatomy_findings_with_llm([_document()], patient_id="p")
        with anatomy_llm._PROVIDER_COOLDOWNS_LOCK:
            anatomy_llm._PROVIDER_COOLDOWNS.clear()

    assert len(calls) == 2
    assert len(anatomy_llm._ANATOMY_RESPONSE_CACHE) == 0


def test_provider_fallback_is_cached_only_after_complete_valid_response(monkeypatch):
    calls = []

    def request(prompt_json, provider, model):
        calls.append(provider)
        if provider == "groq":
            raise RuntimeError("synthetic provider failure")
        return _empty_response(prompt_json, provider, model)

    monkeypatch.setattr(
        anatomy_llm, "_configured_providers",
        lambda: [("groq", "primary"), ("openrouter", "backup")],
    )
    monkeypatch.setattr(anatomy_llm, "_request_uncached", request)

    anatomy_llm.derive_anatomy_findings_with_llm([_document()], patient_id="p")
    anatomy_llm.derive_anatomy_findings_with_llm([_document()], patient_id="p")

    assert calls == ["groq", "openrouter"]


def test_anatomy_lease_uses_separate_patient_lock_namespace():
    from backend.app.detection.run_lock import (
        try_acquire_patient_anatomy_lease,
        try_acquire_patient_detection_lease,
    )

    class Scalar:
        def __init__(self, value):
            self.value = value

        def scalar(self):
            return self.value

    class Connection:
        def __init__(self, engine):
            self.engine = engine

        def execute(self, statement, params):
            query = str(statement)
            key = params["lock_key"]
            if "pg_try_advisory_lock" in query:
                if key in self.engine.held:
                    return Scalar(False)
                self.engine.held.add(key)
                return Scalar(True)
            self.engine.held.discard(key)
            return Scalar(True)

        def commit(self):
            pass

        def close(self):
            pass

        def invalidate(self):
            self.engine.held.clear()

    class Engine:
        held = set()

        def connect(self):
            return Connection(self)

    engine = Engine()
    patient_id = UUID("bb06202c-79bc-58c9-a8d6-be0000000000")
    detection_lease = try_acquire_patient_detection_lease(engine, patient_id)
    anatomy_lease = try_acquire_patient_anatomy_lease(engine, patient_id)
    assert detection_lease is not None
    assert anatomy_lease is not None
    detection_lease.release()
    anatomy_lease.release()


def test_anatomy_lock_conflict_uses_local_rule_fallback(monkeypatch):
    from backend.app.canonical import api

    patient_id = UUID("bb06202c-79bc-58c9-a8d6-be0000000000")
    monkeypatch.setattr(api, "try_acquire_patient_anatomy_lease", lambda *_: None)
    monkeypatch.setattr(api, "get_patient_context", lambda **_: {
        "clinical_documents": [_document(text="Rash on face.")],
        "conditions": [], "observations": [], "lab_results": [],
    })
    monkeypatch.setattr(
        api, "derive_anatomy_findings_with_llm",
        lambda *_args, **_kwargs: pytest.fail("AI must be skipped when another run owns the lock"),
    )

    response = api.get_canonical_patient_anatomy(patient_id, refresh=True, db=object())

    assert response["extraction_method"] == "local_extraction"
    assert response["findings"]


def test_anatomy_lease_releases_after_provider_failure_and_uses_rule_fallback(monkeypatch):
    from backend.app.canonical import api

    class Lease:
        released = False

        def release(self):
            self.released = True

    lease = Lease()
    monkeypatch.setattr(api, "try_acquire_patient_anatomy_lease", lambda *_: lease)
    monkeypatch.setattr(api, "get_patient_context", lambda **_: {
        "clinical_documents": [_document(text="Rash on face.")],
        "conditions": [], "observations": [], "lab_results": [],
    })
    monkeypatch.setattr(
        api, "derive_anatomy_findings_with_llm",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(TimeoutError("synthetic timeout")),
    )

    response = api.get_canonical_patient_anatomy(
        UUID("bb06202c-79bc-58c9-a8d6-be0000000000"), refresh=False, db=object()
    )

    assert lease.released
    assert response["extraction_method"] == "local_extraction"
    assert response["findings"]
