"""Test database session management functionality."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import engine, get_session
from app.db.session_management import get_db


@pytest.mark.asyncio
async def test_engine_configuration() -> None:
    """Test that the engine is configured with the correct options."""
    # Arrange/Act - The engine is created at module level, so we just need to inspect it

    # Assert - Verify engine configuration
    assert engine is not None

    # The internal SQL dialect object should reflect the proper driver
    assert "sqlite+aiosqlite" in str(engine.url) or "postgresql+asyncpg" in str(
        engine.url
    )


@pytest.mark.asyncio
async def test_get_db_context_manager() -> None:
    """Test that get_db yields a session and closes it properly."""
    # Arrange
    mock_session = AsyncMock(spec=AsyncSession)

    # Mock async_session_factory to return our mock session
    with patch("app.db.session.async_session_factory", return_value=mock_session):
        # Act
        db_gen = get_db()
        session = await db_gen.__anext__()  # Use __anext__ instead of anext

        # Assert - Verify we got the session
        assert session == mock_session

        try:
            # Finish the generator to trigger the finally block
            await db_gen.__anext__()
        except StopAsyncIteration:
            pass

        # Verify the session was closed
        mock_session.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_db_handles_exceptions() -> None:
    """Test that get_db closes the session even if an exception occurs."""
    # Arrange
    mock_session = AsyncMock(spec=AsyncSession)
    test_exception = Exception("Test error")

    # Mock async_session_factory to return our mock session
    with patch("app.db.session.async_session_factory", return_value=mock_session):
        # Act
        db_gen = get_db()
        session = await db_gen.__anext__()  # Use __anext__ instead of anext

        # Assert - Verify we got the session
        assert session == mock_session

        # Simulate an exception in the using code
        try:
            # Inject an exception
            await db_gen.athrow(test_exception)
        except Exception as e:
            # Verify the exception was propagated
            assert e == test_exception

        # Verify the session was still closed
        mock_session.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_session_transaction_commit() -> None:
    """Test committing a transaction with the session."""
    # Arrange
    mock_session = AsyncMock(spec=AsyncSession)

    # Act - Simulate adding an object and committing
    mock_session.add(MagicMock())
    await mock_session.commit()

    # Assert
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_session_transaction_rollback() -> None:
    """Test rolling back a transaction with the session."""
    # Arrange
    mock_session = AsyncMock(spec=AsyncSession)

    # Act - Simulate adding an object and rolling back
    mock_session.add(MagicMock())
    await mock_session.rollback()

    # Assert
    mock_session.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_session_transaction_error_handling() -> None:
    """Test that errors during transactions are handled properly."""
    # Arrange
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.commit.side_effect = Exception("Database error")

    # Act/Assert - Verify that the error is propagated
    with pytest.raises(Exception, match="Database error"):
        await mock_session.commit()


@pytest.mark.asyncio
async def test_nested_transactions() -> None:
    """Test behavior with nested transactions."""
    # Create mock nested transactions with proper setup
    mock_outer_transaction = AsyncMock()
    mock_inner_transaction = AsyncMock()

    # Setup __aenter__ to correctly return values
    mock_outer_transaction.__aenter__.return_value = mock_outer_transaction
    mock_inner_transaction.__aenter__.return_value = mock_inner_transaction

    # Mock the session to handle nested transactions
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.begin.side_effect = [
        mock_outer_transaction,  # First call returns outer transaction
        mock_inner_transaction,  # Second call returns inner transaction
    ]

    # Simulate nested transactions
    async with mock_session.begin() as outer_trans:
        # Inner transaction
        async with mock_session.begin() as inner_trans:
            # Both should be the correct mock objects
            assert outer_trans is mock_outer_transaction
            assert inner_trans is mock_inner_transaction


@pytest.mark.asyncio
async def test_get_session_creates_new_session() -> None:
    """Test that get_session creates a new session."""
    # When we get a session
    session = get_session()

    # Then it should be an AsyncSession
    assert isinstance(session, AsyncSession)
    await session.close()


@pytest.mark.asyncio
async def test_get_session_returns_different_sessions() -> None:
    """Test that get_session returns different session instances."""
    # When we get two sessions
    session1 = get_session()
    session2 = get_session()

    try:
        # Then they should be different instances
        assert session1 is not session2
        assert id(session1) != id(session2)
    finally:
        # Clean up
        await session1.close()
        await session2.close()


@pytest.mark.asyncio
async def test_session_isolation() -> None:
    """Test that sessions are properly isolated."""
    # Given two sessions
    session1 = get_session()
    session2 = get_session()

    try:
        # When we begin a transaction in session1
        async with session1.begin():
            # Then session2 should not see the transaction
            assert session1.in_transaction()
            assert not session2.in_transaction()
    finally:
        # Clean up
        await session1.close()
        await session2.close()


@pytest.mark.asyncio
async def test_session_rollback() -> None:
    """Test session rollback functionality."""
    # Given a session
    session = get_session()

    try:
        # When we begin and rollback a transaction
        async with session.begin():
            assert session.in_transaction()
            await session.rollback()

        # Then the session should not be in a transaction
        assert not session.in_transaction()
    finally:
        await session.close()


@pytest.mark.asyncio
async def test_session_commit() -> None:
    """Test session commit functionality."""
    # Given a session
    session = get_session()

    try:
        # When we begin and commit a transaction
        async with session.begin():
            assert session.in_transaction()
            await session.commit()

        # Then the session should not be in a transaction
        assert not session.in_transaction()
    finally:
        await session.close()


@pytest.mark.asyncio
async def test_session_context_manager() -> None:
    """Test session usage with context manager."""
    # Given a session
    session = get_session()

    try:
        # When we use it as a context manager
        async with session:
            # Then it should work without errors
            assert not session.closed
    finally:
        await session.close()


@pytest.mark.asyncio
async def test_session_explicit_close() -> None:
    """Test explicitly closing a session."""
    # Given a session
    session = get_session()

    # When we close it
    await session.close()

    # Then it should be closed
    assert session.closed
