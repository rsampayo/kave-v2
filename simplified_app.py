"""Simplified version of the application to diagnose issues."""

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import engine, get_db

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan events for the FastAPI application."""
    # Startup
    logger.info("Starting simplified application")
    yield
    # Shutdown
    logger.info("Shutting down simplified application")
    await engine.dispose()


app = FastAPI(
    title="Simplified Kave API",
    description="Simplified version for testing",
    lifespan=lifespan,
)


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {"message": "Hello World from simplified app"}


# Create a dependency instance rather than calling the function in the default parameter
get_db_dependency = Depends(get_db)


@app.get("/test-db")
async def test_db(db: AsyncSession = get_db_dependency) -> dict[str, Any]:
    """Test database connection."""
    try:
        result = await db.execute(text("SELECT 1 as test"))
        value = result.scalar()
        return {"database_connection": "success", "test_value": value}
    except Exception as e:
        logger.error(f"Database error: {str(e)}")
        return {"database_connection": "error", "error": str(e)}
