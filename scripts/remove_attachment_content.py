"""
Migration to mark the content column in Attachment model as deprecated.

This script updates the database schema to discourage using the content column
in the Attachment model. We're not removing the column yet to maintain
backward compatibility, but new code should not rely on it being populated.
"""

import logging

from sqlalchemy import Column, LargeBinary, MetaData, Table, text
from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger(__name__)


async def upgrade(engine: AsyncEngine) -> None:
    """
    Mark the content column as nullable if it isn't already.

    Args:
        engine: SQLAlchemy async engine
    """
    try:
        # Check if the column is already nullable
        async with engine.connect() as conn:
            # First, check SQLite vs PostgreSQL
            dialect = engine.dialect.name

            if dialect == "sqlite":
                # SQLite handles nullable differently - we need to inspect the table info
                query = text("PRAGMA table_info(attachments)")
                result = await conn.execute(query)
                columns = result.fetchall()

                # Find the content column and check if it's already nullable
                content_col = next(
                    (col for col in columns if col[1] == "content"), None
                )
                if content_col:
                    is_nullable = (
                        content_col[3] == 0
                    )  # SQLite: notnull = 0 means nullable
                    if is_nullable:
                        logger.info(
                            "Content column is already nullable in SQLite database"
                        )
                        return
                else:
                    logger.warning("Content column not found in attachments table")
                    return

                # For SQLite, we'd need to recreate the table to change nullability
                # This is a complex operation that should be handled by Alembic
                # Here we'll just log that manual intervention might be needed
                logger.warning(
                    "SQLite doesn't support ALTER COLUMN to change nullability. "
                    "Consider using Alembic for a proper migration."
                )
            else:
                # PostgreSQL and most other databases
                metadata = MetaData()
                Table(
                    "attachments",
                    metadata,
                    Column("content", LargeBinary, nullable=True),
                    schema=None,
                )

                # Modify the column to be nullable
                alter_stmt = text(
                    "ALTER TABLE attachments ALTER COLUMN content DROP NOT NULL"
                )
                await conn.execute(alter_stmt)
                await conn.commit()
                logger.info("Successfully updated content column to be nullable")
    except Exception as e:
        logger.error("Error during migration: %s", str(e))
        raise


async def downgrade(engine: AsyncEngine) -> None:
    """
    No downgrade necessary as we're not removing functionality.

    Args:
        engine: SQLAlchemy async engine
    """
    logger.info("No downgrade needed for content column nullability change")
