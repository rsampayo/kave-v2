"""Main FastAPI application module."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.endpoints import attachments, email_webhooks
from app.core.config import settings
from app.db.session import engine

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Lifespan events for the FastAPI application.

    Handles startup and shutdown events.
    Note: Database schema should be managed through Alembic migrations
    before application startup.
    """
    # Startup
    logger.info("Application starting up")

    # App runs here
    yield

    # Shutdown: Close database connections
    await engine.dispose()
    logger.info("Database connections closed")


def create_application() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        FastAPI: The configured application
    """
    app = FastAPI(
        title=settings.PROJECT_NAME,
        description="AI agent platform that processes emails from MailChimp",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # For development - restrict this in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include API routers
    app.include_router(email_webhooks.router)
    app.include_router(attachments.router, prefix="/attachments", tags=["attachments"])

    return app


app = create_application()
