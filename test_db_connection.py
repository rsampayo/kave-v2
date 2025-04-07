#!/usr/bin/env python3
"""Test script to verify database connection."""

import asyncio
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_connection() -> None:
    """Test the database connection with the configured URL."""

    # Print the current database URL
    logger.info(f"Testing connection with URL: {settings.DATABASE_URL}")

    # Ensure the URL has the right dialect for SQLite with async
    database_url = settings.DATABASE_URL
    sqlite_prefix = "sqlite:///"
    aiosqlite_prefix = "sqlite+aiosqlite:///"

    if database_url.startswith(sqlite_prefix) and not database_url.startswith(
        aiosqlite_prefix
    ):
        database_url = database_url.replace(sqlite_prefix, aiosqlite_prefix, 1)
        logger.info(f"Modified URL to use aiosqlite: {database_url}")

    # Create the engine
    engine = create_async_engine(
        database_url,
        echo=True,
        future=True,
    )

    # Try to connect
    try:
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT 1"))
            logger.info(f"Connection successful! Result: {result.scalar()}")

        logger.info("Test completed successfully")
    except Exception as e:
        logger.error(f"Error connecting to database: {str(e)}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(test_connection())
