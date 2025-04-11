"""Pytest configuration file for the FastAPI application tests."""

import json
import os
from datetime import datetime
from typing import Any, AsyncGenerator, Callable, Type
from unittest import mock

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base
from app.integrations.email.client import WebhookClient
from app.main import create_application


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
        db_url = cls.MEMORY_DB_URL if memory_db else cls.TEST_DB_URL
        return create_async_engine(
            db_url,
            echo=False,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,  # Use StaticPool to share connection across sessions
        )


# Use the test database configuration to create engine and session factory
test_engine = TestDatabaseConfig.get_engine()

# Create a test session factory
TestSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    class_=AsyncSession,
    bind=test_engine,
)  # type: ignore[call-overload]


@pytest_asyncio.fixture(scope="session")
async def setup_db() -> AsyncGenerator[None, None]:
    """Set up the test database, creating all tables."""
    async with test_engine.begin() as conn:
        # Drop all tables first to ensure a clean state
        await conn.run_sync(Base.metadata.drop_all)
        # Create all tables defined by models inheriting from Base
        await conn.run_sync(Base.metadata.create_all)

    yield

    # Clean up after all tests
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh database session for testing.

    Each test gets its own session that is rolled back afterward.
    """
    # Create a new session for each test
    session = TestSessionLocal()

    try:
        yield session
        # Rollback any changes that were made
        await session.rollback()
    finally:
        # Close the session
        await session.close()


@pytest_asyncio.fixture
async def isolated_db() -> AsyncGenerator[AsyncSession, None]:
    """Create an isolated in-memory database session for tests requiring full isolation.

    This fixture creates a separate in-memory database for tests that need complete
    isolation from other tests.
    """
    # Create a completely isolated in-memory engine
    isolated_engine = TestDatabaseConfig.get_engine(memory_db=True)

    # Create and initialize the schema
    async with isolated_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create a session factory for this engine
    session_factory = sessionmaker(
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        class_=AsyncSession,
        bind=isolated_engine,
    )  # type: ignore[call-overload]

    # Create the session
    session = session_factory()

    try:
        yield session
        await session.rollback()
    finally:
        await session.close()
        await isolated_engine.dispose()


@pytest.fixture
def app() -> FastAPI:
    """Create a minimal test FastAPI application."""
    # Import create_application here to avoid issues if it was mocked globally
    return create_application()


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """Provide a TestClient instance based on the app fixture."""
    return TestClient(app)


@pytest_asyncio.fixture
async def async_client(app: FastAPI) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Provide an AsyncClient instance for async endpoint testing."""
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


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
def json_encoder() -> Type[json.JSONEncoder]:
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
