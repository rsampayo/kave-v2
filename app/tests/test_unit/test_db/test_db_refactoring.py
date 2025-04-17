"""Test database session refactoring."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.v1.deps.database import get_db as deps_get_db
from app.db.session import get_db as session_get_db


@pytest.mark.asyncio
async def test_get_db_functions_use_same_implementation():
    """Test that both get_db functions point to the same implementation.

    After refactoring, the deps.database.get_db should just be
    importing from session.get_db, meaning they're the same function object.
    """
    assert (
        deps_get_db is session_get_db
    ), "Both get_db functions should be the same object"


@pytest.mark.asyncio
async def test_deps_get_db_structure():
    """Test that deps.get_db creates and closes a session properly using mocks."""
    # Create a mock async session
    mock_session = MagicMock()
    mock_session.close = AsyncMock()
    mock_session.execute = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 1
    mock_session.execute.return_value = mock_result

    # Patch TrackedAsyncSession to return our mock
    with patch("app.db.session.TrackedAsyncSession", return_value=mock_session):
        # Get a session from the deps get_db
        db_gen = deps_get_db()
        db = await anext(db_gen)

        # Verify we got our mock session
        assert db is mock_session

        # Simulate the end of the request context
        try:
            await db_gen.asend(None)
        except StopAsyncIteration:
            pass

        # Verify close was called
        mock_session.close.assert_awaited_once()
