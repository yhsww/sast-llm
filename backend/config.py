from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    llm_provider: str = "openai"

    # OpenAI
    openai_api_key: str | None = None
    openai_chat_model: str = "gpt-4.1"

    # Gemini
    google_api_key: str | None = None
    gemini_model: str = ""

    # Kimi
    kimi_api_key: str | None = None
    kimi_model: str = ""

    # Claude
    anthropic_api_key: str | None = None
    claude_model: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()