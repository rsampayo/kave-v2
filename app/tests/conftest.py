"""Pytest configuration file for the FastAPI application tests."""

# Force SQLite for all tests - patch applied before any imports
import os

# import sys  # Removing unused import
from unittest import mock

# Create test SQLite database path
test_db_dir = os.path.join(os.path.dirname(__file__), "test_data")
os.makedirs(test_db_dir, exist_ok=True)
test_db_path = os.path.join(test_db_dir, "test.db")
test_db_url = f"sqlite+aiosqlite:///{test_db_path}"

# Patch the environment variable directly to ensure SQLite is used
os.environ["DATABASE_URL"] = test_db_url

import importlib  # noqa: E402
import json  # noqa: E402
from collections.abc import AsyncGenerator, Callable  # noqa: E402
from datetime import datetime  # noqa: E402
from typing import Any, cast  # noqa: E402

import httpx  # noqa: E402
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from httpx import ASGITransport  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncEngine,
    AsyncSession,
    create_async_engine,
)
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db.session import Base  # noqa: E402
from app.db.session_management import get_db  # noqa: E402
from app.integrations.email.client import WebhookClient  # noqa: E402
from app.main import create_application  # noqa: E402


# Custom JSON encoder to handle datetime objects
class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


# Test database configuration
class TestDatabaseConfig:
    """Centralized test database configuration."""

    # Test database URL (persistent file-based SQLite for tests)
    TEST_DB_DIR = os.path.join(os.path.dirname(__file__), "test_data")
    os.makedirs(TEST_DB_DIR, exist_ok=True)
    TEST_DB_PATH = os.path.join(TEST_DB_DIR, "test.db")
    TEST_DB_URL = f"sqlite+aiosqlite:///{TEST_DB_PATH}"

    # Alternative in-memory database for isolated tests
    MEMORY_DB_URL = "sqlite+aiosqlite:///:memory:"

    @classmethod
    def get_engine(cls, memory_db: bool = False) -> AsyncEngine:
        """Create an async engine with appropriate settings.

        Args:
            memory_db: If True, use in-memory database for increased isolation

        Returns:
            An async database engine
        """
        # Always use SQLite for tests to avoid PostgreSQL connection issues
        db_url = cls.MEMORY_DB_URL if memory_db else cls.TEST_DB_URL
        return create_async_engine(
            db_url,
            echo=False,
            connect_args={"check_same_thread": False},
            # Disable connection pooling for tests to avoid connection reuse issues
            poolclass=NullPool,
            # Force close connections
            isolation_level="AUTOCOMMIT",
        )


# Create a test session factory function to ensure new engines for each test
def create_test_session() -> tuple[AsyncEngine, AsyncSession]:
    """Create a new engine and session for a test."""
    engine = TestDatabaseConfig.get_engine()
    # Create session maker for AsyncSession
    async_session_maker = sessionmaker(
        class_=AsyncSession,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    # Configure with engine
    async_session_maker.configure(bind=engine)
    # Create a session
    session = cast(AsyncSession, async_session_maker())
    return engine, session


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_db() -> AsyncGenerator[None, None]:
    """Set up the test database structure once for the test session."""
    engine = TestDatabaseConfig.get_engine()

    async with engine.begin() as conn:
        # Drop all tables first to ensure a clean state
        await conn.run_sync(Base.metadata.drop_all)
        # Create all tables defined by models inheriting from Base
        await conn.run_sync(Base.metadata.create_all)

    yield

    # Clean up after all tests
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh database session for testing.

    Each test gets its own session and engine that are closed afterward.
    """
    # Create a completely isolated engine for each test
    engine = TestDatabaseConfig.get_engine()

    try:
        # Create tables for this test
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Create session maker for AsyncSession with explicit connection parameters
        async_session_maker = sessionmaker(
            class_=AsyncSession,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )
        # Configure with engine
        async_session_maker.configure(bind=engine)

        # Create a session and cast to AsyncSession
        session = cast(AsyncSession, async_session_maker())

        yield session
    finally:
        # Ensure session is properly closed
        if session.in_transaction():
            await session.rollback()  # No return value expected
        await session.close()  # No return value expected
        # Dispose engine to ensure connections are fully closed
        await engine.dispose()


@pytest_asyncio.fixture
async def isolated_db() -> AsyncGenerator[AsyncSession, None]:
    """Create an isolated in-memory database session for tests requiring full isolation."""
    # Create a completely isolated in-memory engine
    isolated_engine = TestDatabaseConfig.get_engine(memory_db=True)

    # Create and initialize the schema
    async with isolated_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create a session factory for this engine
    async_session_maker = sessionmaker(
        class_=AsyncSession,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    async_session_maker.configure(bind=isolated_engine)

    # Create the session
    session = cast(AsyncSession, async_session_maker())

    try:
        yield session
    finally:
        await session.close()
        await isolated_engine.dispose()


@pytest.fixture
def app() -> FastAPI:
    """Provide a FastAPI app with test configuration."""
    # Explicitly reload application modules to ensure settings are properly applied
    import app.db.session as db_session_module

    # Reload session module to use the patched settings
    importlib.reload(db_session_module)

    # Create a test application
    test_app = create_application()

    return test_app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """Provide a TestClient instance based on the app fixture."""
    return TestClient(app)


@pytest_asyncio.fixture
async def async_client(app: FastAPI) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Provide an AsyncClient instance for async endpoint testing."""
    # Create an in-memory SQLite database for maximum isolation
    memory_db_url = "sqlite+aiosqlite:///:memory:"

    # Create a dedicated engine for this test with connection pooling disabled
    engine = create_async_engine(
        memory_db_url,
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=NullPool,
    )

    # Override settings to use our in-memory database
    original_db_url = settings.DATABASE_URL
    settings.DATABASE_URL = memory_db_url

    # Override the get_db dependency to use our test session
    original_get_db = app.dependency_overrides.get(get_db)

    # Track session for cleanup
    test_session = None

    async def get_test_db():
        """Create a fresh session for each request in tests."""
        nonlocal test_session

        # Close any existing session
        if test_session is not None:
            if test_session.in_transaction():
                await test_session.rollback()
            await test_session.close()

        # Create session maker for AsyncSession with explicit connection parameters
        test_async_session_maker = sessionmaker(
            class_=AsyncSession,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )
        # Configure with engine
        test_async_session_maker.configure(bind=engine)
        # Create a new session
        test_session = cast(AsyncSession, test_async_session_maker())

        try:
            yield test_session
        finally:
            # We'll handle cleanup in the fixture teardown
            pass

    # Set up the override
    app.dependency_overrides[get_db] = get_test_db

    try:
        # Initialize database tables for this test with a clean slate
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Create the client
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac
    finally:
        # Clean up session if it exists
        if test_session is not None:
            if test_session.in_transaction():
                await test_session.rollback()  # No return value expected
            await test_session.close()  # No return value expected

        # Restore original dependency if there was one
        if original_get_db:
            app.dependency_overrides[get_db] = original_get_db
        else:
            del app.dependency_overrides[get_db]

        # Restore original database URL
        settings.DATABASE_URL = original_db_url

        # Ensure the engine is properly disposed
        await engine.dispose()


@pytest_asyncio.fixture
async def mock_webhook_client() -> AsyncGenerator[mock.AsyncMock, None]:
    """Provide a mocked WebhookClient for testing."""
    client = mock.AsyncMock(spec=WebhookClient)
    yield client


# For backward compatibility
@pytest_asyncio.fixture
async def mock_mailchimp_client() -> AsyncGenerator[mock.AsyncMock, None]:
    """Deprecated: Alias for mock_webhook_client for backward compatibility."""
    async for client in mock_webhook_client():
        yield client


@pytest.fixture
def json_encoder() -> type[json.JSONEncoder]:
    """Return a custom JSON encoder that can handle datetime objects."""
    return CustomJSONEncoder


@pytest.fixture
def mock_factory() -> Callable[[str], mock.MagicMock]:
    """Create a factory function to generate consistently configured mocks.

    This fixture provides a factory function that creates properly configured mocks
    with consistent settings, making test setup more consistent and maintainable.

    Returns:
        A factory function that creates mocks with the given name
    """

    def _create_mock(name: str) -> mock.MagicMock:
        mock_obj = mock.MagicMock(name=name)
        # Configure common mock behaviors if needed
        return mock_obj

    return _create_mock


@pytest.fixture
def async_mock_factory() -> Callable[[str], mock.AsyncMock]:
    """Create a factory function to generate consistently configured async mocks.

    This fixture provides a factory function that creates properly configured
    async mocks with consistent settings.

    Returns:
        A factory function that creates async mocks with the given name
    """

    def _create_async_mock(name: str) -> mock.AsyncMock:
        mock_obj = mock.AsyncMock(name=name)
        # Configure common mock behaviors if needed
        return mock_obj

    return _create_async_mock


# Patch the settings to use SQLite for tests
@pytest.fixture(scope="session", autouse=True)
def patch_settings():
    """Patch settings to use SQLite for tests."""
    # Save original values
    original_db_url = settings.DATABASE_URL

    # Set SQLite URL for testing
    test_db_dir = os.path.join(os.path.dirname(__file__), "test_data")
    os.makedirs(test_db_dir, exist_ok=True)
    test_db_path = os.path.join(test_db_dir, "test.db")
    test_db_url = f"sqlite+aiosqlite:///{test_db_path}"

    # Verify we're using SQLite - if not, set it
    if not settings.DATABASE_URL.startswith("sqlite+aiosqlite://"):
        settings.DATABASE_URL = test_db_url

    # Ensure the database directory exists
    os.makedirs(os.path.dirname(test_db_path), exist_ok=True)

    # Reset the SQLite database
    if os.path.exists(test_db_path):
        try:
            os.unlink(test_db_path)
        except (OSError, PermissionError):
            pass  # Ignore if we can't delete it

    # Yield to allow tests to run
    yield

    # Restore original values
    settings.DATABASE_URL = original_db_url
