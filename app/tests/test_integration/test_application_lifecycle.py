"""Integration tests for application lifecycle management."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from fastapi import FastAPI

from app.main import create_application


@pytest.mark.asyncio
async def test_application_creation() -> None:
    """Test that the application is created with the correct settings and middleware."""
    # Create the application
    app = create_application()

    # Verify app properties
    from app.core.config import settings

    assert app.title == settings.PROJECT_NAME

    # Verify middleware - check by name
    middleware_names = [m.cls.__name__ for m in app.user_middleware]
    assert "CORSMiddleware" in middleware_names

    # Verify routes - check for webhook route pattern
    route_paths = [route.path for route in app.routes]
    assert any("/webhooks" in path for path in route_paths)


@pytest.mark.asyncio
async def test_custom_lifespan_handler() -> None:
    """Test a custom lifespan handler with proper mocking."""
    # Create a simplified lifespan function for testing
    setup_called = False
    cleanup_called = False

    @asynccontextmanager
    async def test_lifespan(_app: FastAPI) -> AsyncIterator[None]:
        nonlocal setup_called, cleanup_called
        # Setup
        setup_called = True
        yield
        # Cleanup
        cleanup_called = True

    # Create app with our test lifespan
    app = FastAPI(lifespan=test_lifespan)

    # Run the lifespan and verify setup/cleanup are called
    async with app.router.lifespan_context(app):
        assert setup_called, "Setup was not called"
        assert not cleanup_called, "Cleanup was called too early"

    assert cleanup_called, "Cleanup was not called"


@pytest.mark.asyncio
async def test_lifespan_error_handling() -> None:
    """Test that errors in the lifespan setup are properly handled."""

    # Create a lifespan that raises an exception during setup
    @asynccontextmanager
    async def error_lifespan(_app: FastAPI) -> AsyncIterator[None]:
        raise ValueError("Setup error")
        yield  # This will never be reached

    # Create app with our error lifespan
    app = FastAPI(lifespan=error_lifespan)

    # Verify the error is propagated
    with pytest.raises(ValueError, match="Setup error"):
        async with app.router.lifespan_context(app):
            pass  # This should not be reached


@pytest.mark.asyncio
async def test_lifespan_cleanup_error_handling() -> None:
    """Test that errors in the lifespan cleanup are properly handled."""
    cleanup_attempted = False

    @asynccontextmanager
    async def cleanup_error_lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
        nonlocal cleanup_attempted
        cleanup_attempted = True
        raise ValueError("Cleanup error")

    # Create app with our cleanup error lifespan
    app = FastAPI(lifespan=cleanup_error_lifespan)

    # Verify cleanup error is propagated
    with pytest.raises(ValueError, match="Cleanup error"):
        async with app.router.lifespan_context(app):
            pass  # Normal execution within context

    assert cleanup_attempted, "Cleanup was not attempted"
