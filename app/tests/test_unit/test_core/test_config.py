"""Unit tests for application settings configuration."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

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
        settings = Settings(
            SECRET_KEY="test_secret",
            DATABASE_URL="sqlite:///./test.db",
            MAILCHIMP_API_KEY="test_api_key",
            MAILCHIMP_WEBHOOK_SECRET="test_webhook_secret",
        )

    # Verify default values
    assert settings.API_ENV == "development"
    assert settings.DEBUG is True
    assert settings.PROJECT_NAME == "Kave"


def test_settings_missing_required_fields() -> None:
    """Test settings initialization fails when required fields are missing."""
    # Attempt to create settings without required fields
    # This should raise a ValidationError from pydantic
    from pydantic import ValidationError

    # Save original environment variables
    original_env = {}
    for key in [
        "SECRET_KEY",
        "DATABASE_URL",
        "MAILCHIMP_API_KEY",
        "MAILCHIMP_WEBHOOK_SECRET",
    ]:
        if key in os.environ:
            original_env[key] = os.environ[key]
            del os.environ[key]

    # Temporarily rename .env file if it exists
    env_path = Path(os.getcwd()) / ".env"
    temp_env_path = Path(os.getcwd()) / ".env.tmp"
    env_renamed = False

    if env_path.exists():
        env_path.rename(temp_env_path)
        env_renamed = True

    try:
        # Now with environment variables and .env removed, initialization should fail
        with pytest.raises(ValidationError):
            Settings()
    finally:
        # Restore original environment variables
        for key, value in original_env.items():
            os.environ[key] = value

        # Restore .env file if it was renamed
        if env_renamed:
            temp_env_path.rename(env_path)


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
    """Test database URL validation for SQLite URLs."""
    # Create a test URL that should be rejected
    sqlite_url = "sqlite:///./test.db"

    # Validate URL using the classmethod directly - should raise ValueError
    with pytest.raises(ValueError, match="SQLite database is not supported"):
        Settings.validate_db_url(sqlite_url)


def test_get_webhook_url_property() -> None:
    """Test the get_webhook_url property returns correct URLs based on environment."""
    # Test production environment
    with patch.dict(
        os.environ,
        {
            "SECRET_KEY": "test_secret",
            "DATABASE_URL": "sqlite:///./test.db",
            "MAILCHIMP_API_KEY": "test_api_key",
            "MAILCHIMP_WEBHOOK_SECRET": "test_webhook_secret",
            "API_ENV": "production",
            "MAILCHIMP_WEBHOOK_BASE_URL_PRODUCTION": "https://api.example.com",
            "MAILCHIMP_WEBHOOK_BASE_URL_TESTING": "https://dev.example.com",
            "WEBHOOK_PATH": "/v1/webhooks/mandrill",
        },
    ):
        settings = Settings(
            SECRET_KEY="test_secret",
            DATABASE_URL="sqlite:///./test.db",
            MAILCHIMP_API_KEY="test_api_key",
            MAILCHIMP_WEBHOOK_SECRET="test_webhook_secret",
        )
        assert (
            settings.get_webhook_url == "https://api.example.com/v1/webhooks/mandrill"
        )

    # Test development environment
    with patch.dict(
        os.environ,
        {
            "SECRET_KEY": "test_secret",
            "DATABASE_URL": "sqlite:///./test.db",
            "MAILCHIMP_API_KEY": "test_api_key",
            "MAILCHIMP_WEBHOOK_SECRET": "test_webhook_secret",
            "API_ENV": "development",
            "MAILCHIMP_WEBHOOK_BASE_URL_PRODUCTION": "https://api.example.com",
            "MAILCHIMP_WEBHOOK_BASE_URL_TESTING": "https://dev.example.com",
            "WEBHOOK_PATH": "/v1/webhooks/mandrill",
        },
    ):
        settings = Settings(
            SECRET_KEY="test_secret",
            DATABASE_URL="sqlite:///./test.db",
            MAILCHIMP_API_KEY="test_api_key",
            MAILCHIMP_WEBHOOK_SECRET="test_webhook_secret",
        )
        assert (
            settings.get_webhook_url == "https://dev.example.com/v1/webhooks/mandrill"
        )


def test_should_reject_unverified_property() -> None:
    """Test the should_reject_unverified property returns correct values based on environment."""
    # Test production environment with rejection enabled
    with patch.dict(
        os.environ,
        {
            "SECRET_KEY": "test_secret",
            "DATABASE_URL": "sqlite:///./test.db",
            "MAILCHIMP_API_KEY": "test_api_key",
            "MAILCHIMP_WEBHOOK_SECRET": "test_webhook_secret",
            "API_ENV": "production",
            "MAILCHIMP_REJECT_UNVERIFIED_PRODUCTION": "true",
            "MAILCHIMP_REJECT_UNVERIFIED_TESTING": "false",
        },
    ):
        settings = Settings(
            SECRET_KEY="test_secret",
            DATABASE_URL="sqlite:///./test.db",
            MAILCHIMP_API_KEY="test_api_key",
            MAILCHIMP_WEBHOOK_SECRET="test_webhook_secret",
        )
        assert settings.should_reject_unverified is True

    # Test development environment with rejection disabled
    with patch.dict(
        os.environ,
        {
            "SECRET_KEY": "test_secret",
            "DATABASE_URL": "sqlite:///./test.db",
            "MAILCHIMP_API_KEY": "test_api_key",
            "MAILCHIMP_WEBHOOK_SECRET": "test_webhook_secret",
            "API_ENV": "development",
            "MAILCHIMP_REJECT_UNVERIFIED_PRODUCTION": "true",
            "MAILCHIMP_REJECT_UNVERIFIED_TESTING": "false",
        },
    ):
        settings = Settings(
            SECRET_KEY="test_secret",
            DATABASE_URL="sqlite:///./test.db",
            MAILCHIMP_API_KEY="test_api_key",
            MAILCHIMP_WEBHOOK_SECRET="test_webhook_secret",
        )
        assert settings.should_reject_unverified is False
