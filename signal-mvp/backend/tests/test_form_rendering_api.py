from io import BytesIO
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient
from pypdf import PdfReader

from backend.app.database import get_db
from backend.app.agents.form_rendering import service as rendering_service
from backend.app.main import app
from backend.app.models.case import Case
from backend.app.models.workflow_records import CaseWorkflowRecord, Report


client = TestClient(app)


class FakeQuery:
    def __init__(self, result):
        self.result = result

    def filter(self, *expressions):
        return self

    def order_by(self, *expressions):
        return self

    def first(self):
        return self.result


class FakeSession:
    def __init__(self, case, workflow_records):
        self.case = case
        self.workflow_records = iter(workflow_records)

    def query(self, model):
        if model is Case:
            return FakeQuery(self.case)
        if model is CaseWorkflowRecord:
            return FakeQuery(next(self.workflow_records))
        raise AssertionError(f"Unexpected query model: {model}")

    def add(self, record):
        if isinstance(record, Report):
            self.report = record

    def commit(self):
        pass

    def refresh(self, record):
        if isinstance(record, Report):
            record.report_id = str(uuid4())
            record.created_at = datetime.now(timezone.utc)


def test_rendered_form_can_be_retrieved_as_pdf(tmp_path, monkeypatch):
    monkeypatch.setattr(rendering_service, "OUTPUT_DIR", tmp_path)
    case_id = uuid4()
    case = SimpleNamespace(
        case_id=case_id,
        jurisdiction="TX",
        disease="measles",
        patient={
            "first_name": "Test",
            "last_name": "Patient",
            "address": "100 Test Street",
            "city": "Austin",
        },
        provider={},
        facility={},
        clinical_evidence={},
        laboratory_evidence=[],
        ai_evidence={},
        report_fields={
            "reporting.investigated_by": "Clinical Staff",
            "reporting.investigating_agency": "County Health",
            "reporting.investigating_agency_email": "staff@example.org",
            "reporting.investigating_agency_phone": "555-0123",
            "reporting.investigation_start_date": "2026-10-01",
        },
    )
    workflow_records = [
        SimpleNamespace(status="APPROVE", payload={"reviewer_id": "reviewer"}),
        SimpleNamespace(status="VALID", payload={"valid": True}),
        SimpleNamespace(status="ATTESTED", payload={"attested_by": "reporter"}),
    ]
    fake_session = FakeSession(case, workflow_records)

    def override_get_db():
        yield fake_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        response = client.post(
            "/api/agents/form-rendering/render",
            json={
                "case_id": str(case_id),
                "form_id": "TX_MEASLES_OUTBREAK_CRF_2025",
                "form_version": "2025-05-07",
                "report_data": {"Last Name": "Test"},
            },
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    rendered = response.json()
    assert rendered["missing_required_fields"] == []
    rendered_values = {item["value"] for item in rendered["fields"]}
    assert {
        "Clinical Staff",
        "County Health",
        "staff@example.org",
        "555-0123",
        "2026-10-01",
    } <= rendered_values
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
