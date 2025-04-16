"""Test suite to verify session management after refactoring."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

# Import session utilities from their respective modules
from app.api.v1.deps.database import get_db as deps_get_db
from app.db.session import TrackedAsyncSession
from app.db.session import get_db as session_get_db
from app.db.session import get_session


@pytest.mark.asyncio
async def test_all_session_functions_work() -> None:
    """Verify that all session management functions create valid sessions."""
    # Test app.api.v1.deps.database.get_db
    deps_db_gen = deps_get_db()
    deps_db = await deps_db_gen.__anext__()
    try:
        assert isinstance(deps_db, AsyncSession)
        # Check for closed attribute if it's a TrackedAsyncSession
        if isinstance(deps_db, TrackedAsyncSession):
            assert not deps_db.closed
    finally:
        try:
            await deps_db_gen.aclose()
        except Exception:
            pass

    # Test app.db.session.get_db
    session_db_gen = session_get_db()
    session_db = await session_db_gen.__anext__()
    try:
        assert isinstance(session_db, AsyncSession)
        # Check for closed attribute if it's a TrackedAsyncSession
        if isinstance(session_db, TrackedAsyncSession):
            assert not session_db.closed
    finally:
        try:
            await session_db_gen.aclose()
        except Exception:
            pass

    # Test app.db.session.get_session
    direct_session = get_session()
    try:
        assert isinstance(direct_session, AsyncSession)
        # Check for closed attribute if it's a TrackedAsyncSession
        if isinstance(direct_session, TrackedAsyncSession):
            assert not direct_session.closed
    finally:
        await direct_session.close()


@pytest.mark.asyncio
async def test_session_factory_isolation() -> None:
    """Verify that each session provider creates isolated sessions."""
    # Get sessions from different factories
    deps_db_gen = deps_get_db()
    session_db_gen = session_get_db()

    deps_db = await deps_db_gen.__anext__()
    session_db = await session_db_gen.__anext__()
    direct_session = get_session()

    try:
        # Verify they're all different session instances
        assert deps_db is not session_db
        assert deps_db is not direct_session
        assert session_db is not direct_session

        # Verify transaction isolation
        async with deps_db.begin():
            assert deps_db.in_transaction()
            assert not session_db.in_transaction()
            assert not direct_session.in_transaction()
    finally:
        try:
            await deps_db_gen.aclose()
            await session_db_gen.aclose()
            await direct_session.close()
        except Exception:
            pass
