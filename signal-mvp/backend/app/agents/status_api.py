import shutil
from pathlib import Path

from fastapi import APIRouter

from backend.app.config.settings import settings
from backend.app.forms.mappings.texas_measles import PDF_FIELD_MAP
router = APIRouter(prefix="/api/agents", tags=["Agent Status"])


def _status(name: str, configured: bool, simulated: bool, description: str, error: str | None = None) -> dict:
    return {
        "agent_name": name,
        "available": True,
        "configured": configured,
        "simulated": simulated,
        "error": error,
        "description": description,
        "last_execution": None,
    }


@router.get("/status")
def get_agent_status() -> dict:
    provider = (settings.llm_provider or "gemini").casefold()
    llm_configured = bool(settings.gemini_api_key if provider == "gemini" else settings.groq_api_key if provider == "groq" else False)
    rules_path = Path(__file__).resolve().parents[1] / "rules" / "rule_catalog.json"
    template_path = Path(__file__).resolve().parents[1] / "forms" / "templates" / "TX_MEASLES_OUTBREAK_CRF_2025.pdf"
    return {
        "agents": [
            _status("document_intelligence", True, False, "Local document text extraction and OCR."),
            _status("nlp_evidence", llm_configured, False, f"Configured provider: {provider}", None if llm_configured else f"No API key configured for {provider}."),
            _status("candidate_fusion", True, False, "Deterministic candidate fusion."),
            _status("cluster_signal", True, False, "Cluster analysis over caller-supplied events."),
            _status("reportability_workflow", rules_path.is_file(), not settings.gemini_enabled, "Local rule evaluation with optional LLM reasoning."),
            _status("deadline_calculation", rules_path.is_file(), False, "Rule-catalog deadline calculation."),
            _status("deadline_escalation", True, False, "Persisted deadline status evaluation."),
            _status("case_assembly", True, False, "Persistent case assembly through the reportability workflow."),
            _status("manual_reporting", bool(PDF_FIELD_MAP), False, "Texas measles reporting preparation."),
            _status("form_rendering", template_path.is_file(), False, "Local PDF form rendering."),
            _status("attestation_control", True, False, "Role-gated human attestation."),
            _status("ecr_submission", True, True, "Submission transport is MOCK_PHA; no real PHA delivery."),
            _status("submission_tracking", True, True, "Reads persisted submission state; destination remains simulated."),
            _status("acknowledgement", True, True, "Generated acknowledgement identifiers are simulated."),
            _status("retry_resubmission", True, True, "Retry records are persisted; transmission is simulated."),
            _status("audit_ledger", True, False, "Persisted workflow audit events."),
        ]
    }
