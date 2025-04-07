"""Simple database tests to verify the infrastructure."""

from typing import Any

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.tests.test_models import SimpleModel


@pytest.mark.asyncio
async def test_db_connection(db_session: AsyncSession) -> None:
    """Test that the database connection works."""
    # Run a simple query
    result = await db_session.execute(text("SELECT 1"))
    assert result.scalar() == 1, "Database connection failed"


@pytest.mark.asyncio
async def test_orm_operations(db_session: AsyncSession, setup_db: Any) -> None:
    """Test that ORM operations work."""
    # Create a new record
    test_record = SimpleModel(id=1, name="Test Record")
    db_session.add(test_record)

    # Explicitly flush to the database without committing
    await db_session.flush()

    # Query it back
    result = await db_session.execute(select(SimpleModel).where(SimpleModel.id == 1))
    record = result.scalar_one()

    # Verify
    assert record.name == "Test Record", "ORM operations failed"
