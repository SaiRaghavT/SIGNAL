from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    # Database
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "signal"
    db_user: str = "postgres"
    db_password: str
    gemini_enabled: bool = False
    llm_provider: str = "gemini"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.8-flash"
    groq_api_key: str | None = None
    groq_run_detection_api_key: str | None = None
    groq_anatomy_api_key: str | None = None
    groq_model: str = "openai/gpt-oss-20b"
    openrouter_api_key: str | None = None
    openrouter_model: str = "openai/gpt-oss-20b"
    # Keep independent Run Detection requests conservative by default. Set to 1
    # to force the previous sequential behavior.
    detection_ai_max_concurrency: int = 2
    # Anatomy/model extraction uses an independent conservative provider cap.
    anatomy_ai_max_concurrency: int = 2
    # Evidence-strength policy weights (0-100 scale). These are review aids,
    # not validated clinical probabilities.
    evidence_strength_structured_base: float = Field(default=60.0, ge=0, le=100)
    evidence_strength_document_base: float = Field(default=50.0, ge=0, le=100)
    evidence_strength_multiple_symptoms_base: float = Field(default=40.0, ge=0, le=100)
    evidence_strength_exposure_base: float = Field(default=35.0, ge=0, le=100)
    evidence_strength_single_symptom_base: float = Field(default=25.0, ge=0, le=100)
    evidence_strength_quote_bonus: float = Field(default=10.0, ge=0, le=100)
    evidence_strength_additional_source_bonus: float = Field(default=5.0, ge=0, le=100)
    evidence_strength_max_source_bonus: float = Field(default=15.0, ge=0, le=100)
    evidence_strength_cross_source_bonus: float = Field(default=5.0, ge=0, le=100)
    tesseract_cmd: str | None = None
    # Destructive demo workflow reset is disabled unless explicitly opted in.
    demo_mode: bool = False
    # Allows synthetic source records to be staged in Admin Queue for demos.
    # Demo queue entries are tagged and cannot be dispatched externally.
    demo_queue_enabled: bool = False

    # Optional Epic FHIR R4 sandbox connection. Credentials stay server-side.
    epic_client_id: str | None = None
    epic_token_url: str = "https://fhir.epic.com/interconnect-fhir-oauth/oauth2/token"
    epic_fhir_base_url: str = "https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4"
    epic_patient_identifier_system: str = "urn:oid:1.2.840.114350.1.13.0.1.7.5.737384.14"
    epic_private_key_path: str | None = None
    epic_jwks_url: str | None = None
    epic_jwt_kid: str | None = None
    epic_http_timeout_seconds: float = 20.0
    # Raw FHIR Bundles contain patient data and are hidden unless explicitly enabled.
    epic_raw_response_enabled: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
