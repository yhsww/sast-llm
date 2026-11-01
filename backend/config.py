from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    
    llm_provider: str = "openai"

    openai_api_key: str | None = None
    openai_chat_model: str = "GPT5.5"

    google_api_key: str | None = None
    gemini_model: str = "Gemini"

    kimi_api_key: str | None = None
    kimi_model: str = "Kimi"

    anthropic_api_key: str | None = None
    claude_model: str = "Claude"

    model_config = SettingsConfigDict(
        env_file=ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
