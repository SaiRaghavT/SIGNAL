from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.assistant.api import router


def test_chat_fails_closed_even_with_forged_demo_session_headers():
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    response = client.post(
        "/api/assistant/chat",
        json={"question": "Summarize patient P-1024"},
        headers={
            "X-SIGNAL-Demo-Context": '{"logged_in":true,"role":"Administrator"}'
        },
    )

    assert response.status_code == 503
    assert "server-side user authentication" in response.json()["detail"]
    assert "No patient records were accessed" in response.json()["detail"]
