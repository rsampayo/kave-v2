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
