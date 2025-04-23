"""Pytest configuration file for the FastAPI application tests."""

# Force PostgreSQL for all tests - patch applied before any imports
import importlib
import json
import logging
import os
from collections.abc import AsyncGenerator, Callable
from datetime import datetime
from typing import Any, cast
from unittest import mock

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.db.session import Base, get_db
from app.integrations.email.client import WebhookClient
from app.main import create_application

# Create test PostgreSQL URL
test_db_url = "postgresql://ramonsampayo:postgres@localhost:5432/kave_test"

# Patch the environment variable directly to ensure PostgreSQL is used
os.environ["DATABASE_URL"] = test_db_url

# Setup logger for test configurations
logger = logging.getLogger(__name__)


# Custom JSON encoder to handle datetime objects
class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


# Test database configuration
class TestDatabaseConfig:
    """Centralized test database configuration."""

    # Test database URL using PostgreSQL
    TEST_DB_URL = "postgresql+asyncpg://rsampayo:postgres@localhost:5432/kave_test"

    # Alternative test database
    ISOLATED_TEST_DB_URL = (
        "postgresql+asyncpg://rsampayo:postgres@localhost:5432/kave_test_isolated"
    )

    @classmethod
    def get_engine(cls, isolated_db: bool = False) -> AsyncEngine:
        """Create an async engine with appropriate settings.

        Args:
            isolated_db: If True, use isolated database for increased isolation

        Returns:
            An async database engine
        """
        # Always use PostgreSQL for tests
        db_url = cls.ISOLATED_TEST_DB_URL if isolated_db else cls.TEST_DB_URL
        return create_async_engine(
            db_url,
            echo=False,
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

    try:
        # Ensure tables exist but handle in a separate connection
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Ensure we're starting with a clean session
        if session.in_transaction():
            await session.rollback()

        yield session
    finally:
        # Ensure session is properly closed
        try:
            if session.in_transaction():
                await session.rollback()
            await session.close()
        except Exception as e:
            logger.warning(f"Error during session cleanup: {e}")
        finally:
            # Dispose engine to ensure connections are fully closed
            await engine.dispose()


@pytest_asyncio.fixture
async def isolated_db() -> AsyncGenerator[AsyncSession, None]:
    """Create an isolated in-memory database session for tests requiring full isolation."""
    # Create a completely isolated in-memory engine
    isolated_engine = TestDatabaseConfig.get_engine(isolated_db=True)

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


@pytest.fixture
def mock_current_user() -> Any:
    """Create a mock user for authentication testing."""
    from app.models.user import User

    # Create a user with superuser rights for full access
    user = mock.MagicMock(spec=User)
    user.id = 1
    user.username = "testuser"
    user.email = "test@example.com"
    user.is_active = True
    user.is_superuser = True
    return user


@pytest_asyncio.fixture(scope="function")
async def async_client(
    app: FastAPI, mock_current_user: Any
) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Provide an AsyncClient instance for async endpoint testing."""
    # Create an isolated PostgreSQL database for maximum isolation
    isolated_test_db_url = (
        "postgresql+asyncpg://rsampayo:postgres@localhost:5432/kave_test_isolated"
    )

    # Create a dedicated engine for this test with connection pooling disabled
    engine = create_async_engine(
        isolated_test_db_url,
        echo=False,
        poolclass=NullPool,
        # Force close connections
        isolation_level="AUTOCOMMIT",
    )

    # Override settings to use our isolated PostgreSQL database
    original_db_url = settings.DATABASE_URL
    settings.DATABASE_URL = isolated_test_db_url

    # Override the get_db dependency to use our test session
    original_get_db = app.dependency_overrides.get(get_db)

    # Override the authentication dependency
    from app.api.v1.deps.auth import get_current_active_user

    original_get_current_user = app.dependency_overrides.get(get_current_active_user)
    app.dependency_overrides[get_current_active_user] = lambda: mock_current_user

    # Create session maker for each request
    test_async_session_maker = async_sessionmaker(
        class_=AsyncSession,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        bind=engine,
    )

    async def get_test_db():
        """Create a fresh session for each request in tests."""
        # Create a new session for each request
        session = test_async_session_maker()

        try:
            yield session
        finally:
            # Properly close session after each request
            try:
                if session.in_transaction():
                    await session.rollback()
                await session.close()
            except Exception as e:
                logger.warning(f"Error closing session: {e}")

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
        # Restore original dependency if there was one
        if original_get_db:
            app.dependency_overrides[get_db] = original_get_db
        else:
            del app.dependency_overrides[get_db]

        # Restore original user dependency
        if original_get_current_user:
            app.dependency_overrides[get_current_active_user] = (
                original_get_current_user
            )
        else:
            del app.dependency_overrides[get_current_active_user]

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


# Patch the settings to use PostgreSQL for tests
@pytest.fixture(scope="session", autouse=True)
def patch_settings():
    """Patch settings to use PostgreSQL for tests."""
    # Save original values
    original_db_url = settings.DATABASE_URL

    # Set PostgreSQL URL for testing
    test_db_url = "postgresql://rsampayo:postgres@localhost:5432/kave_test"

    # Verify we're using PostgreSQL - if not, set it
    if not settings.DATABASE_URL.startswith("postgresql+asyncpg://"):
        settings.DATABASE_URL = test_db_url

    # Yield to allow tests to run
    yield

    # Restore original values
    settings.DATABASE_URL = original_db_url


@pytest.fixture(autouse=True)
def celery_eager():
    """Configure Celery to execute tasks eagerly (synchronously) during tests."""
    try:
        from app.worker.celery_app import celery_app

        # Store original configuration
        original_task_always_eager = celery_app.conf.task_always_eager
        original_task_eager_propagates = celery_app.conf.task_eager_propagates

        # Set eager execution for tests
        celery_app.conf.task_always_eager = True
        celery_app.conf.task_eager_propagates = True

        yield celery_app

        # Restore original configuration
        celery_app.conf.task_always_eager = original_task_always_eager
        celery_app.conf.task_eager_propagates = original_task_eager_propagates
    except ImportError:
        # If celery is not installed or app is not found, skip this fixture
        pytest.skip("Celery not available")
        yield None
