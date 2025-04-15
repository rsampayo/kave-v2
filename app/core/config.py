"""Configuration settings module for Kave application.

This module defines the application settings and configuration options
using Pydantic's BaseSettings for environment variable loading.
"""

from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings configuration.

    Uses pydantic BaseSettings to load config from environment variables.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",  # Ignore extra fields in .env
    )

    # API
    API_ENV: str = "development"
    DEBUG: bool = True
    SECRET_KEY: str
    PROJECT_NAME: str = "Kave"

    # Database
    DATABASE_URL: str
    SQL_ECHO: bool = False

    # MailChimp
    MAILCHIMP_API_KEY: str
    MAILCHIMP_WEBHOOK_SECRET: str

    # Default Organization (for backwards compatibility)
    DEFAULT_ORGANIZATION_NAME: str = "Default Organization"
    DEFAULT_ORGANIZATION_EMAIL: str = "webhooks@example.com"

    # File Storage
    ATTACHMENTS_BASE_DIR: Path = Path("data/attachments")

    # S3 Storage
    S3_BUCKET_NAME: str = ""
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"
    USE_S3_STORAGE: bool = False

    # Ngrok settings (for webhook testing)
    NGROK_AUTH_TOKEN: str = ""
    NGROK_REGION: str = "us"
    NGROK_LOCAL_PORT: int = 8000
    WEBHOOK_PATH: str = "/v1/webhooks/mandrill"

    # Webhook configuration
    MAILCHIMP_WEBHOOK_BASE_URL_PRODUCTION: str = ""
    MAILCHIMP_WEBHOOK_BASE_URL_TESTING: str = ""
    MAILCHIMP_REJECT_UNVERIFIED_PRODUCTION: bool = False
    MAILCHIMP_REJECT_UNVERIFIED_TESTING: bool = False
    MAILCHIMP_WEBHOOK_ENVIRONMENT: str = "testing"  # Options: "production", "testing"

    @property
    def is_production_environment(self) -> bool:
        """Determine if we're running in a production environment.

        Returns:
            bool: True if in production or staging
        """
        return self.API_ENV in ("production", "staging")

    @property
    def should_reject_unverified(self) -> bool:
        """Determine if unverified webhooks should be rejected.

        Returns:
            bool: True if unverified webhooks should be rejected
        """
        if self.is_production_environment:
            return self.MAILCHIMP_REJECT_UNVERIFIED_PRODUCTION
        return self.MAILCHIMP_REJECT_UNVERIFIED_TESTING

    @property
    def get_webhook_url(self) -> str:
        """Get the full webhook URL for the current environment.

        Returns:
            str: The complete webhook URL for the current environment
        """
        base_url = (
            self.MAILCHIMP_WEBHOOK_BASE_URL_PRODUCTION
            if self.is_production_environment
            else self.MAILCHIMP_WEBHOOK_BASE_URL_TESTING
        )

        # Check if the base URL already includes the webhook path
        path = self.WEBHOOK_PATH
        if not path.startswith("/"):
            path = f"/{path}"

        # If the base URL already includes the path, don't append it again
        if base_url.endswith(path):
            return base_url

        return f"{base_url}{path}"

    @classmethod
    @field_validator("DATABASE_URL")
    def validate_db_url(cls, v: str) -> str:
        """Validate and normalize the database URL.

        This ensures SQLite URLs are prefixed with 'sqlite:///' if not already,
        and validates PostgreSQL URLs.
        """
        if v.startswith("postgres://"):
            v = v.replace("postgres://", "postgresql://", 1)
        return v


# settings will be initialized from environment variables or .env file
settings = Settings()
