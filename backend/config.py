from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    
    llm_provider: str = "openai"

    openai_api_key: str | None = None
    openai_chat_model: str = "gpt-4.1"

    google_api_key: str | None = None
    gemini_model: str = "gemini-3.8"

    kimi_api_key: str | None = None
    kimi_model: str = "moonshot-v1-8k"

    anthropic_api_key: str | None = None
    claude_model: str = "claude-sonnet-4-5"

    model_config = SettingsConfigDict(
        env_file=ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
