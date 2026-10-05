from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def test_candidate_disposition_api_is_registered_and_deterministic():
    response = client.post(
        "/api/candidate/disposition",
        json={
            "candidate_id": "candidate-api-test",
            "laboratory_decision": "POSITIVE",
            "rule_decision": "REPORT",
            "jurisdiction_status": "RESOLVED",
            "reportability_decision": "PROCEED_TO_RULES",
        },
    )

    assert response.status_code == 200
    assert response.json()["final_decision"] == "REPORT"


def test_document_intelligence_api_is_registered():
    response = client.post(
        "/api/agents/document-intelligence/process",
        json={"documents": [{"document_id": "doc-1", "text": "Fever and rash reported."}]},
    )

    assert response.status_code == 200
    assert response.json()["documents"][0]["text"] == "Fever and rash reported."


def test_nlp_evidence_api_returns_empty_for_no_documents_without_llm():
    response = client.post(
        "/api/agents/nlp-evidence/extract",
        json={"documents": []},
    )

    assert response.status_code == 200
    assert response.json() == {"evidence": []}


def test_nlp_evidence_api_returns_extracted_evidence(monkeypatch):
    monkeypatch.setattr(
        "backend.app.agents.nlp_evidence.router.extract_evidence",
        lambda documents: [{"evidence_type": "symptom", "concept": "fever"}],
    )
    response = client.post(
        "/api/agents/nlp-evidence/extract",
        json={"documents": [{"document_id": "doc-2", "text": "Patient has fever."}]},
    )

    assert response.status_code == 200
    assert response.json() == {
        "evidence": [{"evidence_type": "symptom", "concept": "fever"}]
    }
