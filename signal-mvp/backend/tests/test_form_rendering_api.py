from io import BytesIO

from fastapi.testclient import TestClient
from pypdf import PdfReader

from backend.app.agents.form_rendering import service as rendering_service
from backend.app.main import app


client = TestClient(app)


def test_rendered_form_can_be_retrieved_as_pdf(tmp_path, monkeypatch):
    monkeypatch.setattr(rendering_service, "OUTPUT_DIR", tmp_path)

    response = client.post(
        "/api/agents/form-rendering/render",
        json={
            "case_id": "CASE-PDF-TEST",
            "form_id": "TX_MEASLES_OUTBREAK_CRF_2025",
            "form_version": "2025-05-07",
            "report_data": {"Last Name": "Test"},
        },
    )

    assert response.status_code == 200
    rendered = response.json()
    render_id = rendered["render_id"]
    retrieval_url = f"/api/agents/form-rendering/{render_id}"
    assert rendered["retrieval_url"] == retrieval_url
    assert rendered["rendered_document"] == retrieval_url
    assert (tmp_path / f"{render_id}{rendering_service.RENDERED_FILE_SUFFIX}").is_file()

    pdf_response = client.get(retrieval_url)

    assert pdf_response.status_code == 200
    assert pdf_response.headers["content-type"] == "application/pdf"
    assert pdf_response.content.startswith(b"%PDF-")
    assert len(PdfReader(BytesIO(pdf_response.content)).pages) > 0


def test_unknown_or_invalid_render_id_returns_404():
    missing = client.get("/api/agents/form-rendering/" + "0" * 32)
    invalid = client.get("/api/agents/form-rendering/not-a-render-id")

    assert missing.status_code == 404
    assert invalid.status_code == 404
    assert rendering_service.get_rendered_pdf_path("../outside.pdf") is None