from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # LLM provider: openai, gemini, kimi, or claude
    llm_provider: str = "kimi"

    # OpenAI — chat and embeddings
    openai_api_key: str = ""
    openai_chat_model: str = "gpt-6.1-sol"
    openai_embedding_model: str = "text-embedding-3-small"

    # Google Gemini
    google_api_key: str = ""
    gemini_model: str = "gemini-3.8-pro"

    # Kimi
    kimi_api_key: str = ""
    kimi_model: str = "kimi-k3.1-pro"

    # Anthropic Claude
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-5"

    # ChromaDB — RAG configuration
    chroma_persist_path: str = "./chroma_data"
    chroma_collection_cwe: str = "cwe_docs"
    chroma_collection_wstg: str = "wstg_docs"
    top_k_cwe: int = 2
    top_k_wstg: int = 2

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
