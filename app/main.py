"""Main FastAPI application module with improved lifespan error handling."""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import IntegrityError

from app.api.v1 import api_v1_router
from app.core.config import settings
from app.services.initialization_service import InitializationService

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
    """Lifespan events for the FastAPI application with improved error handling.

    Handles startup and shutdown events, including proper handling of
    asyncio.CancelledError which can occur during uvicorn shutdown.
    Note: Database schema should be managed through Alembic migrations
    before application startup.
    """
    # Startup
    logger.info("Application starting up")

    # Initialize default data
    try:
        logger.info("Initializing application data")
        # Get a database session
        from app.db.session import async_session_factory

        async with async_session_factory() as db:
            init_service = InitializationService(db)
            await init_service.initialize()
            logger.info("Application data initialization completed")
    except asyncio.CancelledError:
        # Handle cancellation during startup
        logger.warning("Startup canceled - this is expected during some shutdowns")
        # Re-raise to let uvicorn handle it properly
        raise
    except Exception as e:
        logger.error(f"Failed to initialize application data: {str(e)}")

    try:
        # App runs here
        yield
    except asyncio.CancelledError:
        # Handle cancellation during runtime
        logger.warning(
            "Application execution canceled - this is expected during shutdown"
        )
        # Re-raise to let uvicorn handle it properly
        raise
    finally:
        # Shutdown: Close database connections
        # This will run regardless of normal exit or cancellation
        try:
            logger.info("Application shutdown - cleaning up resources")
            from app.db.session import engine

            await engine.dispose()
            logger.info("Database connections closed")
        except Exception as e:
            logger.error(f"Error during shutdown cleanup: {str(e)}")


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

    # Mount static files directory
    static_dir = Path(__file__).parent / "static"
    app.mount(
        "/static", StaticFiles(directory=str(static_dir), html=True), name="static"
    )

    # Add global exception handlers
    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(
        request: Request, exc: IntegrityError
    ) -> JSONResponse:
        """Handle database integrity errors.

        This provides user-friendly error messages for constraint violations.
        """
        logger.error(f"Database integrity error: {str(exc)}")

        error_msg = str(exc)
        detail = "Database constraint violation occurred"
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR

        # Check for specific constraint violations
        if (
            "uq_organizations_mandrill_webhook_secret" in error_msg
            or "mandrill_webhook_secret" in error_msg
        ):
            detail = "Organization with the same webhook secret already exists. "
            detail += "This is a security risk."
            status_code = status.HTTP_409_CONFLICT
        elif "ix_organizations_name" in error_msg:
            detail = "Organization with the same name already exists"
            status_code = status.HTTP_409_CONFLICT
        elif "unique constraint" in error_msg.lower():
            detail = "A record with the same unique values already exists"
            status_code = status.HTTP_409_CONFLICT

        return JSONResponse(
            status_code=status_code,
            content={"detail": detail},
        )

    # Include API v1 router
    app.include_router(api_v1_router)

    return app


app = create_application()
