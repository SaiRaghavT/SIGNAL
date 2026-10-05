from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "signal"
    db_user: str = "postgres"
    db_password: str
    gemini_enabled: bool = False
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"

    # LLM provider
    # Supported values: "gemini" or "groq"
    llm_provider: str = "groq"

    # Gemini
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.8-flash"

    # Groq
    groq_api_key: str | None = None
    groq_model: str = "openai/gpt-oss-20b"

    # OCR
    tesseract_cmd: str | None = None
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
