"""Configuration settings module for Kave application.

This module defines the application settings and configuration options
using Pydantic's BaseSettings for environment variable loading.
"""

from pathlib import Path
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings configuration.

    Uses pydantic BaseSettings to load config from environment variables.
    Required environment variables (app will fail to start if missing):
    - SECRET_KEY: Secret key for security functions
    - DATABASE_URL: Database connection string
    - MAILCHIMP_API_KEY: API key for MailChimp integration
    - MAILCHIMP_WEBHOOK_SECRET: Secret for webhook verification
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
    SECRET_KEY: str  # Required
    PROJECT_NAME: str = "Kave"

    # Authentication
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    # First superuser credentials for initial setup
    FIRST_SUPERUSER_USERNAME: Optional[str] = None
    FIRST_SUPERUSER_EMAIL: Optional[str] = None
    FIRST_SUPERUSER_PASSWORD: Optional[str] = None

    # Database
    DATABASE_URL: str  # Required
    KAVE_DATABASE_URL: Optional[str] = None
    SQL_ECHO: bool = False

    # MailChimp
    MAILCHIMP_API_KEY: str  # Required
    MAILCHIMP_WEBHOOK_SECRET: str  # Required

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

    # Celery configuration
    CELERY_BROKER_URL: str = Field(
        default="redis://localhost:6379/0",
        description="URL for the Celery broker (Redis)",
    )
    CELERY_RESULT_BACKEND: str = Field(
        default="redis://localhost:6379/0",
        description="URL for the Celery result backend (Redis)",
    )
    # For Heroku compatibility
    REDIS_URL: Optional[str] = Field(
        default=None, description="Redis URL provided by Heroku add-on"
    )

    # PDF Processing Configuration
    PDF_BATCH_COMMIT_SIZE: int = Field(
        default=10,
        description="Number of pages to process before committing. "
        "Set to 0 for single transaction per PDF.",
    )
    PDF_USE_SINGLE_TRANSACTION: bool = Field(
        default=False,
        description="If True, processes entire PDF in a single transaction.",
    )
    PDF_MAX_ERROR_PERCENTAGE: float = Field(
        default=10.0,
        description="Maximum percentage of pages that can fail before task fails.",
    )

    # Tesseract Configuration
    TESSERACT_PATH: str = Field(
        default="/usr/local/bin/tesseract",  # Default macOS Homebrew path
        description="Path to Tesseract executable",
    )
    TESSERACT_LANGUAGES: List[str] = Field(
        default=["eng"], description="Languages to use for OCR"
    )

    @property
    def is_production_environment(self) -> bool:
        """Return True if the environment is configured for production.

        Returns:
            bool: True for production, False otherwise
        """
        return self.API_ENV.lower() == "production"

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
        """Get the complete webhook URL for the current environment.

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

    @property
    def effective_database_url(self) -> str:
        """Get the effective database URL, prioritizing KAVE_DATABASE_URL if set.

        This is critical for Heroku deployments where DATABASE_URL may be overridden
        by a custom configuration.

        Returns:
            str: The validated and normalized database URL to use
        """
        # Use KAVE_DATABASE_URL if set (contains Heroku's DATABASE_URL)
        db_url = self.KAVE_DATABASE_URL or self.DATABASE_URL

        # Apply validation
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)

        # Prevent using SQLite in any environment - PostgreSQL only
        if db_url.startswith("sqlite://"):
            raise ValueError(
                "SQLite database is not supported. "
                "Please configure a PostgreSQL database using DATABASE_URL."
            )

        return db_url

    @property
    def effective_tesseract_path(self) -> str:
        """Get the effective tesseract path based on environment.
        
        For Heroku deployments, if the path is not explicitly configured,
        default to the apt buildpack installation path.
        
        Returns:
            str: The path to the tesseract executable
        """
        import os
        import platform
        
        # Use explicit path if set
        if self.TESSERACT_PATH and os.path.exists(self.TESSERACT_PATH):
            return self.TESSERACT_PATH
            
        # Check for Heroku environment
        if os.environ.get("DYNO"):
            return "/app/.apt/usr/bin/tesseract"
            
        # Platform-specific defaults
        if platform.system() == "Darwin":  # macOS
            return "/usr/local/bin/tesseract"
        elif platform.system() == "Linux":
            return "/usr/bin/tesseract"
        else:
            return "tesseract"  # Hope it's in PATH

    @classmethod
    @field_validator("DATABASE_URL")
    def validate_db_url(cls, v: str) -> str:
        """Validate and normalize the database URL.

        This ensures PostgreSQL URLs are properly formatted.
        SQLite URLs are not supported.
        """
        if v.startswith("postgres://"):
            v = v.replace("postgres://", "postgresql://", 1)

        # Prevent using SQLite in any environment
        if v.startswith("sqlite://"):
            raise ValueError(
                "SQLite database is not supported. "
                "Please configure a PostgreSQL database using DATABASE_URL."
            )

        return v


# settings will be initialized from environment variables or .env file
# The application will fail to start if required settings are not provided
settings = Settings()
