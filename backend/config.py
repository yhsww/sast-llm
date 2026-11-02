import os
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    llm_provider: Literal["openai", "gemini", "kimi", "claude"] = "openai"

    openai_api_key: str | None = None
    openai_chat_model: str = "gpt-6.1-sol"

    google_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("GOOGLE_API_KEY", "GEMINI_API_KEY"),
    )
    gemini_model: str = "gemini-3.8-pro"

    kimi_api_key: str | None = None
    kimi_model: str = "kimi-k3.1-pro"

    anthropic_api_key: str | None = None
    claude_model: str = "claude-sonnet-5"


settings = Settings()
