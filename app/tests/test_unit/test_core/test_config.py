"""Unit tests for application settings configuration."""

import os
from unittest.mock import patch

from app.core.config import Settings


def test_settings_model_config() -> None:
    """Test that Settings has the correct model configuration."""
    # Access the model_config directly from the Settings class
    config = Settings.model_config

    # Verify model_config has expected values
    assert config.get("env_file") == ".env"
    assert config.get("env_file_encoding") == "utf-8"
    assert config.get("case_sensitive") is True


def test_settings_default_values() -> None:
    """Test default values are set correctly in Settings."""
    # Create settings instance with minimal environment variables
    with patch.dict(
        os.environ,
        {
            "SECRET_KEY": "test_secret",
            "DATABASE_URL": "sqlite:///./test.db",
            "MAILCHIMP_API_KEY": "test_api_key",
            "MAILCHIMP_WEBHOOK_SECRET": "test_webhook_secret",
        },
    ):
        settings = Settings()

    # Verify default values
    assert settings.API_ENV == "development"
    assert settings.DEBUG is True
    assert settings.PROJECT_NAME == "Kave"


def test_validate_db_url_postgresql() -> None:
    """Test database URL validation for PostgreSQL URLs."""
    # Create a test URL
    postgres_url = "postgres://user:pass@localhost:5432/testdb"
    expected_url = "postgresql://user:pass@localhost:5432/testdb"

    # Validate URL using the classmethod directly
    result = Settings.validate_db_url(postgres_url)

    # Verify URL was converted correctly
    assert result == expected_url


def test_validate_db_url_unchanged() -> None:
    """Test database URL validation for non-PostgreSQL URLs."""
    # Create a test URL that shouldn't be changed
    sqlite_url = "sqlite:///./test.db"

    # Validate URL using the classmethod directly
    result = Settings.validate_db_url(sqlite_url)

    # Verify URL remains unchanged
    assert result == sqlite_url
