from pydantic_settings import BaseSettings, SettingsConfigDict


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
    groq_model: str = "openai/gpt-oss-20b"
    tesseract_cmd: str | None = None
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    # Destructive demo workflow reset is disabled unless explicitly opted in.
    demo_mode: bool = False
    # Allows synthetic source records to be staged in Admin Queue for demos.
    # Demo queue entries are tagged and cannot be dispatched externally.
    demo_queue_enabled: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
