#!/usr/bin/env python3
"""Utility script to check for PDFs with missing text content and reprocess them.

This script will:
1. Find all PDF attachments in the database
2. Check which ones don't have corresponding text content
3. Process those PDFs using the direct processor
"""

import asyncio
import logging
import sys
from typing import List, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from app.db.session import async_session_factory
from app.models.attachment_text_content import AttachmentTextContent
from app.models.email_data import Attachment
from process_pdf_directly import process_pdf_directly_async

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def find_pdfs_missing_text() -> List[Tuple[int, str]]:
    """Find PDF attachments that don't have any text content records.

    Returns:
        List[Tuple[int, str]]: List of (attachment_id, filename) tuples
    """
    async with async_session_factory() as db:
        # Find PDF attachments
        pdf_query = select(Attachment).where(
            Attachment.content_type == "application/pdf"
        )
        result = await db.execute(pdf_query)
        pdf_attachments = result.scalars().all()

        missing_text = []

        # Check each PDF attachment for text content
        for attachment in pdf_attachments:
            count_query = select(func.count(AttachmentTextContent.id)).where(
                AttachmentTextContent.attachment_id == attachment.id
            )
            result = await db.execute(count_query)
            count = result.scalar()

            if count == 0:
                missing_text.append(
                    (attachment.id, attachment.filename or "unknown.pdf")
                )
                logger.info(
                    f"Found PDF without text content: ID={attachment.id}, Filename={attachment.filename}"
                )

        return missing_text


async def fix_pdfs_missing_text() -> None:
    """Find and fix PDF attachments with missing text content."""
    pdfs_to_fix = await find_pdfs_missing_text()

    if not pdfs_to_fix:
        logger.info("No PDFs with missing text content found")
        return

    logger.info(f"Found {len(pdfs_to_fix)} PDFs with missing text content")

    for attachment_id, filename in pdfs_to_fix:
        logger.info(f"Processing attachment ID={attachment_id}, Filename={filename}")

        try:
            # Use the direct processor instead of Celery
            success = await process_pdf_directly_async(attachment_id)

            if success:
                logger.info(f"✅ Successfully processed attachment ID={attachment_id}")
            else:
                logger.error(f"❌ Failed to process attachment ID={attachment_id}")
        except Exception as e:
            logger.error(f"❌ Error processing attachment ID={attachment_id}: {e}")


def main() -> None:
    """Run the fix script."""
    print("PDF Text Content Fix Utility")
    print("============================")

    # Run the async function
    asyncio.run(fix_pdfs_missing_text())

    print("\nProcess complete. Check logs for details.")


if __name__ == "__main__":
    main()
