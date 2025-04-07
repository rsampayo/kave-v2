"""Migration script for transferring existing attachments to S3.

This script migrates attachments from database content column to S3 storage.
Run it after the database schema migration is complete.
"""

import asyncio
import base64
import logging
from typing import List

from sqlalchemy import select

from app.db.session import engine, get_session, init_db
from app.models.email_data import Attachment
from app.services.storage_service import StorageService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def migrate_existing_attachments() -> None:
    """Migrate all existing attachments to S3 storage."""
    logger.info("Starting attachment migration to S3/filesystem storage...")

    # Initialize database if needed
    await init_db()
    logger.info("Database initialized")

    # Initialize services
    storage = StorageService()

    # Use a new session for the migration
    session = get_session()
    async with session:
        # Get all attachments with content data but no storage_uri
        query = select(Attachment).where(
            Attachment.content.is_not(None),
            (Attachment.storage_uri.is_(None) | Attachment.storage_uri == ""),
        )
        result = await session.execute(query)
        attachments = result.scalars().all()

        logger.info(f"Found {len(attachments)} attachments to migrate")

        for i, attachment in enumerate(attachments):
            try:
                # Generate object key
                object_key = f"attachments/{attachment.email_id}/{attachment.id}_{attachment.filename}"

                # Skip if no content
                if not attachment.content:
                    logger.warning(
                        f"Attachment {attachment.id} has no content to migrate, skipping"
                    )
                    continue

                # Upload to storage
                storage_uri = await storage.save_file(
                    file_data=attachment.content,
                    object_key=object_key,
                    content_type=attachment.content_type,
                )

                # Update the attachment record
                attachment.storage_uri = storage_uri

                # Log progress periodically
                if (i + 1) % 10 == 0 or i == len(attachments) - 1:
                    logger.info(f"Migrated {i + 1}/{len(attachments)} attachments")

            except Exception as e:
                logger.error(f"Error migrating attachment {attachment.id}: {str(e)}")
                # Continue with next attachment even if one fails

        # Commit all changes at once
        await session.commit()

    # Close the engine
    await engine.dispose()
    logger.info("Attachment migration completed")


if __name__ == "__main__":
    asyncio.run(migrate_existing_attachments())
