"""Main FastAPI application module."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_v1_router
from app.core.config import settings
from app.db.session import engine, get_session
from app.services.initialization_service import InitializationService
from app.services.organization_service import OrganizationService

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Set more specific logging levels for signature verification modules
logging.getLogger("app.integrations.email.client").setLevel(logging.DEBUG)
logging.getLogger("app.api.v1.endpoints.webhooks.mandrill.router").setLevel(
    logging.DEBUG
)
logging.getLogger("app.api.v1.endpoints.webhooks.mandrill.processors").setLevel(
    logging.DEBUG
)

# Log handler to make signature verification logs stand out
signature_handler = logging.StreamHandler()
signature_handler.setFormatter(
    logging.Formatter(
        "%(asctime)s - 🔑 SIGNATURE - %(name)s - %(levelname)s - %(message)s"
    )
)
signature_logger = logging.getLogger("app.integrations.email.client")
signature_logger.addHandler(signature_handler)
signature_logger.propagate = False  # Prevent duplicate logs


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Lifespan events for the FastAPI application.

    Handles startup and shutdown events.
    Note: Database schema should be managed through Alembic migrations
    before application startup.
    """
    # Startup
    logger.info("Application starting up")

    # Initialize default data
    try:
        logger.info("Initializing default organization")
        db = get_session()
        org_service = OrganizationService(db)
        init_service = InitializationService(db, org_service)
        await init_service.init_default_organization()
        await db.close()
        logger.info("Default data initialization completed")
    except Exception as e:
        logger.error(f"Failed to initialize default data: {str(e)}")

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

    # Include API v1 router
    app.include_router(api_v1_router)

    return app


app = create_application()
