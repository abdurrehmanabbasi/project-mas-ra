"""Unit tests for configuration management."""

from app.config import Settings, get_settings


def test_settings_defaults():
    """Verify default configuration attributes are appropriately populated."""
    settings = Settings()
    assert settings.APP_ENV in ["development", "testing", "production"]
    assert settings.OPENAI_MODEL_NAME == "gpt-4o-mini"
    assert settings.OPENAI_EMBEDDING_MODEL == "text-embedding-3-small"
    assert settings.MAX_PAPERS_PER_TASK == 10
    assert settings.SEARCH_TIMEOUT_SECONDS == 15
    assert "postgresql" in settings.DATABASE_URL


def test_get_settings_cached():
    """Verify get_settings returns a singleton cached instance."""
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2

