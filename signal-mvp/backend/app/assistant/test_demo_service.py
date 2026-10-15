from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.assistant.api import demo_router, router
from backend.app.assistant.demo_service import DEMO_LABEL, chat_with_synthetic_demo


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.include_router(demo_router)
    return TestClient(app)


def test_each_static_demo_patient_returns_labeled_structured_summary():
    for patient_id in ("DEMO-P001", "DEMO-P002", "DEMO-P003"):
        result = chat_with_synthetic_demo(f"Summarize patient {patient_id}")
        assert result["status"] == "summary"
        assert result["selected_patient_id"] == patient_id
        assert result["label"] == DEMO_LABEL
        assert result["sections"]


def test_demo_lookup_by_name_and_id():
    assert chat_with_synthetic_demo("Give me the summary for Alex Morgan")["selected_patient_id"] == "DEMO-P001"
    assert chat_with_synthetic_demo("DEMO-P002")["selected_patient_id"] == "DEMO-P002"


def test_unknown_and_real_patient_identifiers_never_match():
    for query in ("Summarize patient DEMO-P999", "Summarize patient P-1024", "Summarize patient 1f8b4384-cb39-6fab-3ca5-adb869c3ab03"):
        result = chat_with_synthetic_demo(query)
        assert result["status"] == "no_match"
        assert result["label"] == DEMO_LABEL


def test_ambiguous_name_requires_explicit_patient_selection():
    result = chat_with_synthetic_demo("Give me the summary for Morgan")
    assert result["status"] == "selection_required"
    assert {item["patient_id"] for item in result["candidates"]} == {"DEMO-P001", "DEMO-P002"}


def test_followup_uses_only_valid_selected_synthetic_patient():
    result = chat_with_synthetic_demo("Explain the reporting deadline", "DEMO-P001")
    assert result["selected_patient_id"] == "DEMO-P001"
    assert result["label"] == DEMO_LABEL

    unknown = chat_with_synthetic_demo("Explain the reporting deadline", "P-1024")
    assert unknown["status"] == "needs_patient"


def test_demo_endpoint_does_not_query_or_mutate_database(monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("Demo endpoint must not access the database")

    monkeypatch.setattr(Session, "query", forbidden)
    monkeypatch.setattr(Session, "add", forbidden)
    monkeypatch.setattr(Session, "commit", forbidden)
    response = _client().post("/api/assistant/demo/chat", json={"question": "Summarize patient DEMO-P001"})
    assert response.status_code == 200
    assert response.json()["label"] == DEMO_LABEL


def test_demo_endpoint_has_no_real_workflow_side_effects_or_real_patient_fallback():
    response = _client().post("/api/assistant/demo/chat", json={"question": "Summarize patient P-1024"})
    assert response.status_code == 200
    assert response.json()["status"] == "no_match"
    assert "submission" not in response.json()


def test_production_endpoint_remains_fail_closed():
    response = _client().post("/api/assistant/chat", json={"question": "Summarize patient DEMO-P001"})
    assert response.status_code == 503
    assert "server-side user authentication" in response.json()["detail"]
