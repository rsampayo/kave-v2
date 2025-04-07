"""Pytest configuration file for the FastAPI application tests."""

import json
import os
from datetime import datetime
from typing import Any, AsyncGenerator, Type
from unittest import mock

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base
from app.integrations.email.client import MailchimpClient
from app.main import create_application


# Custom JSON encoder to handle datetime objects
class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


# Test database URL (persistent file-based SQLite for tests)
TEST_DB_DIR = os.path.join(os.path.dirname(__file__), "test_data")
os.makedirs(TEST_DB_DIR, exist_ok=True)
TEST_DB_PATH = os.path.join(TEST_DB_DIR, "test.db")
TEST_DB_URL = f"sqlite+aiosqlite:///{TEST_DB_PATH}"

# Use a separate engine for testing with connection pooling
test_engine = create_async_engine(
    TEST_DB_URL,
    echo=False,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,  # Use StaticPool to share connection across sessions
)

# Create a test session factory
TestSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    class_=AsyncSession,
    bind=test_engine,
)  # type: ignore[call-overload]

# Use pytest-asyncio's built-in event loop instead of creating our own
# This avoids the deprecation warning


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
async def mock_mailchimp_client() -> AsyncGenerator[MailchimpClient, None]:
    """Provide a mocked MailchimpClient for testing."""
    client = mock.AsyncMock(spec=MailchimpClient)
    # Configure default behaviors
    client.verify_webhook_signature.return_value = True
    yield client


@pytest.fixture
def json_encoder() -> Type[json.JSONEncoder]:
    """Return a custom JSON encoder that can handle datetime objects."""
    return CustomJSONEncoder
