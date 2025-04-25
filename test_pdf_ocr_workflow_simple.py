#!/usr/bin/env python3
"""Test script for the complete PDF OCR workflow using direct database operations.

This script simulates processing a PDF document through the OCR system:
1. Creates a mock attachment record directly in the database
2. Triggers the OCR process directly
3. Uses Redis for monitoring
4. Verifies the OCR results are correctly stored in the database
"""

import asyncio
import base64
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import RedisService
from app.db.session import async_session_factory, engine
from app.models.attachment_text_content import AttachmentTextContent
from app.models.email_data import Attachment, Email
from app.services.storage_service import StorageService
from app.worker.tasks import process_pdf_attachment

# Path to sample PDF for testing
SAMPLE_PDF_PATH = Path(
    "/Users/rsampayo/Documents/Proyectos/Kave/app/tests/test_integration/test_data/sample.pdf"
)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def create_test_records() -> Optional[Attachment]:
    """Create test email and attachment records directly in the database.

    Returns:
        Optional[Attachment]: The created attachment record or None if failed
    """
    # Read the PDF file
    try:
        with open(SAMPLE_PDF_PATH, "rb") as f:
            pdf_content = f.read()
    except FileNotFoundError:
        logger.error(f"Sample PDF not found at: {SAMPLE_PDF_PATH}")
        return None

    # Save the PDF to storage
    storage_service = StorageService()
    attachment_path = f"test_attachments/test_doc_{int(time.time())}.pdf"
    uri = await storage_service.save_file(
        pdf_content, attachment_path, content_type="application/pdf"
    )

    logger.info(f"Saved PDF to storage at: {uri}")

    # Create database records
    async with async_session_factory() as db:
        # Create an email record
        email = Email(
            message_id=f"test-{int(time.time())}@example.com",
            from_email="test@example.com",
            from_name="Test Sender",
            to_email="recipient@example.com",
            subject="Test Email with PDF Attachment",
            body_text="This is a test email with a PDF attachment.",
            body_html="<p>This is a test email with a PDF attachment.</p>",
            received_at=datetime.utcnow(),
            webhook_id=f"test-webhook-{int(time.time())}",
            webhook_event="inbound_email",
        )
        db.add(email)
        await db.flush([email])

        # Create an attachment record
        attachment = Attachment(
            email_id=email.id,
            filename="test-document.pdf",
            content_type="application/pdf",
            size=len(pdf_content),
            storage_uri=uri,
        )
        db.add(attachment)
        await db.commit()

        logger.info(f"Created test email record with ID: {email.id}")
        logger.info(f"Created test attachment record with ID: {attachment.id}")

        return attachment


async def trigger_ocr_processing(attachment_id: int) -> None:
    """Trigger OCR processing for the attachment.

    Args:
        attachment_id: ID of the attachment to process
    """
    logger.info(f"Triggering OCR processing for attachment ID: {attachment_id}")

    # Call the process_pdf_attachment task directly
    # Since this is a test script, we run it synchronously
    task_result = process_pdf_attachment(attachment_id)

    logger.info(f"OCR task completed with result: {task_result}")


async def wait_for_ocr_completion(
    attachment_id: int, timeout: int = 60
) -> List[AttachmentTextContent]:
    """Wait for OCR to complete and return the extracted text content.

    Args:
        attachment_id: The ID of the attachment to check
        timeout: Maximum time to wait in seconds

    Returns:
        List[AttachmentTextContent]: The extracted text content records
    """
    start_time = time.time()
    ocr_results = []

    # Create a database session
    async with async_session_factory() as db:
        while time.time() - start_time < timeout:
            # Query for OCR content
            query = sa.select(AttachmentTextContent).where(
                AttachmentTextContent.attachment_id == attachment_id
            )
            result = await db.execute(query)
            ocr_content = result.scalars().all()

            if ocr_content:
                logger.info(f"OCR completed for attachment ID: {attachment_id}")
                return ocr_content

            logger.info(f"OCR still in progress for attachment ID: {attachment_id}...")

            # Wait before checking again
            await asyncio.sleep(2)

    logger.warning(
        f"Timeout waiting for OCR completion for attachment ID: {attachment_id}"
    )
    return []


async def print_ocr_results(ocr_results: List[AttachmentTextContent]) -> None:
    """Print the OCR results to the console.

    Args:
        ocr_results: List of OCR result records
    """
    if not ocr_results:
        logger.warning("No OCR results to display")
        return

    print("\n📄 OCR Results:")
    print("==============")

    for result in ocr_results:
        print(f"Page {result.page_number}: {result.content[:100]}...")

    print(f"\nTotal pages processed: {len(ocr_results)}")


async def monitor_redis_activity() -> None:
    """Monitor and print Redis activity related to the OCR task."""
    redis = RedisService()

    print("\n📊 Redis Activity:")
    print("================")

    # List all keys with 'celery' pattern
    keys = []
    try:
        keys = redis.redis.keys("celery*")
        if keys:
            print(f"Found {len(keys)} Celery-related keys in Redis")
            for key in keys:
                value = redis.get(key)
                if value:
                    try:
                        # Try to parse as JSON
                        value_data = json.loads(value)
                        print(f"{key}: {json.dumps(value_data, indent=2)[:200]}...")
                    except json.JSONDecodeError:
                        print(f"{key}: {value[:100]}...")
                else:
                    print(f"{key}: <None>")
        else:
            print("No Celery-related keys found in Redis")
    except Exception as e:
        print(f"Error reading Redis keys: {e}")


async def main() -> None:
    """Run the complete PDF OCR workflow test."""
    print("\n🧪 PDF OCR Workflow Test")
    print("======================")
    print(f"Using sample PDF: {SAMPLE_PDF_PATH}")

    if not SAMPLE_PDF_PATH.exists():
        logger.error(f"Sample PDF file not found at {SAMPLE_PDF_PATH}")
        print(f"❌ Sample PDF file not found at {SAMPLE_PDF_PATH}")
        return

    try:
        # Step 1: Create test records
        print("\n📝 Creating test records...")
        attachment = await create_test_records()

        if not attachment:
            print("❌ Failed to create test records")
            return

        print(f"✅ Test records created successfully (Attachment ID: {attachment.id})")

        # Step 2: Trigger OCR processing
        print("\n🔄 Triggering OCR processing...")
        await trigger_ocr_processing(attachment.id)
        print("✅ OCR processing triggered")

        # Step 3: Wait for OCR to complete
        print("\n⏳ Waiting for OCR to complete...")
        ocr_results = await wait_for_ocr_completion(attachment.id)

        if ocr_results:
            print(
                f"✅ OCR completed successfully with {len(ocr_results)} pages processed"
            )

            # Step 4: Display OCR results
            await print_ocr_results(ocr_results)

            # Step 5: Monitor Redis
            await monitor_redis_activity()

            print("\n✨ Complete workflow test passed successfully!")
        else:
            print("❌ OCR did not complete. Check the logs for details.")

    except Exception as e:
        logger.exception("Error in OCR workflow test")
        print(f"\n❌ Test failed with error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
