"""Main FastAPI application module."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.endpoints import email_webhooks
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
    """
    # Startup: Create database tables if they don't exist
    from app.db.session import Base

    async with engine.begin() as conn:
        # Create tables if they don't exist
        await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created or already exist")

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

    return app


app = create_application()
