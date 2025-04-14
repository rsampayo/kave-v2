"""Integration tests for the main FastAPI application."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import fastapi.routing
import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.main import create_application, lifespan, settings


def test_app_creation_and_structure() -> None:
    """Test that create_application correctly configures the FastAPI app."""
    # Call the actual application factory
    test_app = create_application()

    # Verify app type and basic properties
    assert isinstance(test_app, FastAPI)
    assert test_app.title == settings.PROJECT_NAME
    assert test_app.version == "0.1.0"

    # Verify lifespan function is set
    # Note: FastAPI sets the lifespan on the router
    assert test_app.router.lifespan_context == lifespan

    # Verify CORS middleware is added
    # Explicitly check app.user_middleware for CORSMiddleware
    found_cors = False
    for m in test_app.user_middleware:
        # Check the class directly
        if m.cls == CORSMiddleware:
            found_cors = True
            break
    assert found_cors, "CORSMiddleware not found in user_middleware"

    # Verify the email_webhooks router is included under the v1 path
    route_found = False
    for route in test_app.routes:
        if isinstance(route, fastapi.routing.APIRoute) and route.path.startswith(
            "/v1/webhooks"
        ):
            route_found = True
            break
    assert route_found, "Email webhooks router routes not found in app.routes"


@pytest.mark.asyncio
async def test_lifespan_events() -> None:
    """Test the lifespan context manager calls engine methods correctly."""
    # Set up mocks
    mock_conn = AsyncMock()
    mock_conn.run_sync = AsyncMock()

    # Create a proper async context manager mock
    @asynccontextmanager
    async def mock_async_context() -> AsyncGenerator[AsyncMock, None]:
        yield mock_conn

    mock_engine = AsyncMock()
    mock_engine.begin = mock_async_context
    mock_engine.dispose = AsyncMock()

    # Mock Base.metadata
    mock_metadata = MagicMock()
    mock_base = MagicMock()
    mock_base.metadata = mock_metadata
    mock_base.metadata.create_all = MagicMock()

    # Apply mocks with patches
    with patch("app.main.engine", mock_engine), patch("app.db.session.Base", mock_base):
        # Create a dummy FastAPI app
        dummy_app = MagicMock()

        # Execute the lifespan context manager
        async with lifespan(dummy_app):
            # No run_sync assertion - we've removed auto table creation
            # in favor of using Alembic migrations
            pass

        # Verify that after exiting the context, the dispose method was called
        mock_engine.dispose.assert_awaited_once()
