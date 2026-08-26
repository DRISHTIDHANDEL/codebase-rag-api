from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- App ---
    APP_NAME: str = "codebase-rag-api"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # --- Database ---
    DATABASE_URL: str

    # --- Redis ---
    REDIS_URL: str

    # --- Celery ---
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str

    # --- OpenAI / Embeddings ---
    OPENAI_API_KEY: str
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    LLM_MODEL: str = "gpt-4o-mini"

    # --- Cache ---
    SEARCH_CACHE_TTL: int = 3600

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# Create ONE global instance — every other file imports this,
# instead of re-reading the .env file over and over.
settings = Settings()