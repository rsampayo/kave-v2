#!/usr/bin/env python
"""
Helper script to process PDF attachments directly without Celery.
"""

import asyncio
import logging
import sys

import fitz

from app.db.session import async_session_factory
from app.models.attachment_text_content import AttachmentTextContent
from app.models.email_data import Attachment
from app.services.storage_service import StorageService

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def process_pdf_directly_async(attachment_id: int) -> bool:
    """Process a PDF attachment directly without using Celery - async version.

    Args:
        attachment_id: ID of the attachment to process

    Returns:
        bool: True if successful, False otherwise
    """
    logger.info(f"Starting direct PDF processing for attachment {attachment_id}")

    # Create a new async session
    async with async_session_factory() as db:
        try:
            # Get attachment
            attachment = await db.get(Attachment, attachment_id)
            if not attachment:
                logger.error(f"Attachment {attachment_id} not found")
                return False

            if not attachment.storage_uri:
                logger.error(f"Attachment {attachment_id} has no storage URI")
                return False

            logger.info(
                f"Retrieved attachment: {attachment.filename} from {attachment.storage_uri}"
            )

            # Get file from storage
            storage = StorageService()
            pdf_data = await storage.get_file(attachment.storage_uri)
            if not pdf_data:
                logger.error(f"Failed to get PDF data from {attachment.storage_uri}")
                return False

            logger.info(f"Retrieved PDF data ({len(pdf_data)} bytes)")

            # Process PDF
            doc = fitz.open(stream=pdf_data, filetype="pdf")
            logger.info(f"Opened PDF with {doc.page_count} pages")

            # Process each page
            for page_num in range(doc.page_count):
                page = doc.load_page(page_num)
                text = page.get_text("text")

                # Create text content record
                text_content = AttachmentTextContent(
                    attachment_id=attachment.id,
                    page_number=page_num + 1,  # 1-based page numbers
                    text_content=text.strip() if text else None,
                )

                db.add(text_content)
                logger.info(
                    f"Processed page {page_num + 1}/{doc.page_count}, text length: {len(text)}"
                )

            # Commit the changes
            await db.commit()
            logger.info(
                f"Successfully saved text content for all {doc.page_count} pages"
            )

            return True

        except Exception as e:
            logger.error(f"Error in direct PDF processing: {e}")
            # Ensure we rollback on error
            await db.rollback()
            return False


def process_pdf_directly(attachment_id: int) -> bool:
    """Process a PDF attachment directly without using Celery - sync wrapper.

    Args:
        attachment_id: ID of the attachment to process

    Returns:
        bool: True if successful, False otherwise
    """
    return asyncio.run(process_pdf_directly_async(attachment_id))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <attachment_id>")
        sys.exit(1)

    attachment_id = int(sys.argv[1])
    success = process_pdf_directly(attachment_id)

    if success:
        print(f"Successfully processed attachment {attachment_id}")
        sys.exit(0)
    else:
        print(f"Failed to process attachment {attachment_id}")
        sys.exit(1)
