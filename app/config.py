"""Application configuration and settings management."""

from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration settings loaded from environment or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application Environment
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"

    # LLM Settings
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL_NAME: str = "gpt-4o-mini"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"

    # Academic Search APIs
    SEMANTIC_SCHOLAR_API_KEY: Optional[str] = None
    ARXIV_REQUEST_DELAY_SECONDS: float = 3.0

    # PostgreSQL Database
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "research_db"
    POSTGRES_PORT: int = 5432
    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/research_db"

    # Research Execution Limits
    MAX_PAPERS_PER_TASK: int = 10
    SEARCH_TIMEOUT_SECONDS: int = 15
    MAX_REVISION_CYCLES: int = 2

    # LangSmith Tracing & Observability
    LANGSMITH_TRACING: bool = False
    LANGSMITH_API_KEY: Optional[str] = None
    LANGSMITH_PROJECT: str = "mas-research-assistant"


@lru_cache()
def get_settings() -> Settings:
    """Return cached application settings instance."""
    return Settings()

