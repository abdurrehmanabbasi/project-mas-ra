"""Application configuration and settings management."""

from functools import lru_cache
import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Always load .env from repository root into os.environ
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
if _ENV_PATH.exists():
    load_dotenv(dotenv_path=_ENV_PATH, override=True)


class Settings(BaseSettings):
    """Central configuration settings loaded from environment or .env file."""

    model_config = SettingsConfigDict(
        env_file=str(_ENV_PATH),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application Environment
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    API_AUTH_KEY: Optional[str] = None

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
    MAX_PDF_SIZE_MB: int = 15
    PDF_DOWNLOAD_TIMEOUT_SECONDS: int = 15

    # LangSmith Tracing & Observability
    LANGSMITH_TRACING: bool = False
    LANGSMITH_API_KEY: Optional[str] = None
    LANGSMITH_PROJECT: str = "mas-research-assistant"


@lru_cache()
def get_settings() -> Settings:
    """Return cached application settings instance."""
    return Settings()

