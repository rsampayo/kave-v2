from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

# Import with the name expected by the test using direct import for patchability
import app.db.session


# Function need to be imported from app.db.session_management
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency function to get a database session.

    Yields an async session for use in FastAPI dependency injection.
    Ensures the session is closed after use.
    """
    # Get the session from the factory - this is the line that gets patched in tests
    # Use the direct import explicitly to support patching
    session = app.db.session.async_session_factory()

    try:
        # Return the session to the caller
        yield session
    finally:
        # Close the session
        await session.close()
