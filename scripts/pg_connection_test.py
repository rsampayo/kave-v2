#!/usr/bin/env python3
"""
PostgreSQL Connection Test Script

This script verifies that PostgreSQL connection works properly for Heroku deployment.
It attempts to connect to a PostgreSQL database and perform basic operations.
"""

import asyncio
import logging
import os
import sys
from datetime import datetime

from sqlalchemy import Column, Integer, String, Text, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Default database URL for local testing
DEFAULT_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/kave_test"

# Create base class for SQLAlchemy models
Base = declarative_base()


# Test model
class TestModel(Base):
    __tablename__ = "pg_test"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(String(50), nullable=False)


async def test_postgres_connection(database_url: str = None) -> bool:
    """Test PostgreSQL connection using SQLAlchemy.

    Args:
        database_url: Database URL to connect to, defaults to env value or test value

    Returns:
        bool: True if the connection is successful, False otherwise
    """
    # Get database URL from environment variable or use default
    db_url = database_url or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)

    # Handle Heroku-style postgres:// URLs
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
        logger.info("Converted postgres:// URL to postgresql:// format")

    try:
        # Log just the host part of the URL or a placeholder for privacy
        connection_info = db_url.split("@")[1] if "@" in db_url else "[Redacted URL]"
        logger.info(f"Testing connection to: {connection_info}")

        # Create engine
        engine = create_async_engine(db_url, echo=False)

        # Create tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Created test table successfully")

        # Create a test session
        async with AsyncSession(engine) as session:
            # Insert a test record
            timestamp = datetime.now().isoformat()
            test_record = TestModel(
                name="Test PostgreSQL Connection",
                description="Testing PostgreSQL connection for Heroku deployment",
                created_at=timestamp,
            )
            session.add(test_record)
            await session.commit()
            logger.info("Inserted test record successfully")

            # Query the record
            result = await session.execute(
                select(TestModel).where(TestModel.name == "Test PostgreSQL Connection")
            )
            record = result.scalars().first()

            if record and record.created_at == timestamp:
                logger.info("Retrieved test record successfully")
            else:
                logger.error("Failed to retrieve test record correctly")
                return False

            # Clean up
            await session.delete(record)
            await session.commit()
            logger.info("Deleted test record successfully")

        # Clean up tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            logger.info("Dropped test table successfully")

        logger.info("✅ PostgreSQL connection test passed!")
        return True

    except Exception as e:
        logger.error(f"PostgreSQL connection test failed: {str(e)}")
        return False


if __name__ == "__main__":
    # Allow passing a database URL as a command-line argument
    db_url = sys.argv[1] if len(sys.argv) > 1 else None

    success = asyncio.run(test_postgres_connection(db_url))
    if not success:
        sys.exit(1)  # Exit with error code
    sys.exit(0)  # Exit with success code
