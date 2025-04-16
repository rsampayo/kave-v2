"""Module providing Session functionality for the db."""

from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base

from app.core.config import settings

# Create base class for SQLAlchemy models
Base = declarative_base()

# Database configuration
DATABASE_URL = settings.effective_database_url

# Ensure we're not using SQLite in any environment
if DATABASE_URL.startswith("sqlite://"):
    raise ValueError(
        "SQLite database is not supported. "
        "Please configure a PostgreSQL database using DATABASE_URL."
    )

# Ensure postgresql dialect for postgres with asyncpg driver
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
else:
    raise ValueError(
        "Unsupported database type. Only PostgreSQL is supported. "
        "Please configure a PostgreSQL database using DATABASE_URL."
    )

# Create async engine instance
engine: AsyncEngine = create_async_engine(
    DATABASE_URL, echo=settings.SQL_ECHO, future=True
)

# Create session factory
async_session_factory = async_sessionmaker(
    engine, autocommit=False, autoflush=False, expire_on_commit=False
)


class TrackedAsyncSession(AsyncSession):
    """Subclass of AsyncSession that tracks when a session is closed."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._closed = False

    @property
    def closed(self) -> bool:
        """Return True if the session is closed."""
        return self._closed

    async def close(self) -> None:
        """Close the session and mark it as closed."""
        await super().close()
        self._closed = True


async def init_db() -> None:
    """Initialize the database, creating all tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get a database session for dependency injection.

    Yields:
        AsyncSession: Database session

    Example:
        ```python
        @app.get("/users")
        async def get_users(db: AsyncSession = Depends(get_db)):
            # Use db here
            pass
        ```
    """
    async_session = TrackedAsyncSession(
        bind=engine, expire_on_commit=False, autoflush=False, autocommit=False
    )
    try:
        yield async_session
    finally:
        await async_session.close()


def get_session() -> TrackedAsyncSession:
    """Get a new database session.

    Used in cases where dependency injection is not available.

    Returns:
        TrackedAsyncSession: Database session
    """
    return TrackedAsyncSession(
        bind=engine, expire_on_commit=False, autoflush=False, autocommit=False
    )
