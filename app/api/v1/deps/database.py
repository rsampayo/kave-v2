"""Database dependencies for dependency injection."""

from collections.abc import AsyncGenerator
from typing import TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import TrackedAsyncSession, engine

T = TypeVar("T")

__all__ = ["get_db"]


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get a database session for dependency injection.

    This dependency yields a SQLAlchemy AsyncSession that will be
    automatically closed when the request is complete.

    Yields:
        AsyncSession: Database session for use in API endpoints

    Example:
        ```python
        @app.get("/users")
        async def get_users(db: AsyncSession = Depends(get_db)):
            # Query users from the database
            result = await db.execute(select(User))
            users = result.scalars().all()
            return users
        ```

    Raises:
        Exception: Any exceptions from database operations are propagated
    """
    async_session = TrackedAsyncSession(
        bind=engine, expire_on_commit=False, autoflush=False, autocommit=False
    )
    try:
        yield async_session
    finally:
        await async_session.close()
