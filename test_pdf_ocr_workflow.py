#!/usr/bin/env python3
"""Test script for the complete PDF OCR workflow.

This script simulates the entire workflow:
1. Creates a mock email with a PDF attachment
2. Processes the email through the system
3. Uses Redis for task queuing and coordination
4. Verifies the OCR results are correctly stored in the database
"""

import asyncio
import base64
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import RedisService
from app.db.session import async_session_factory
from app.models.attachment_text_content import AttachmentTextContent
from app.models.email_data import Attachment, Email
from app.schemas.webhook_schemas import EmailAttachment as SchemaEmailAttachment
from app.schemas.webhook_schemas import InboundEmailData, MailchimpWebhook, WebhookData
from app.services.attachment_service import AttachmentService
from app.services.email_service import EmailService
from app.services.storage_service import StorageService
from app.worker.celery_app import celery_app
from app.worker.tasks import process_pdf_attachment

# Path to sample PDF for testing
SAMPLE_PDF_PATH = (
    Path(__file__).parent
    / "app"
    / "tests"
    / "test_integration"
    / "test_data"
    / "sample.pdf"
)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def create_test_webhook_payload(pdf_path: Path) -> Dict[str, Any]:
    """Create a test webhook payload with a PDF attachment.

    Args:
        pdf_path: Path to the PDF file to use as an attachment

    Returns:
        Dict: The webhook payload as a dictionary
    """
    # Read the PDF file
    with open(pdf_path, "rb") as f:
        pdf_content = f.read()

    # Create an attachment with the PDF content
    attachment = {
        "name": "test-document.pdf",
        "type": "application/pdf",
        "content": base64.b64encode(pdf_content).decode("utf-8"),
        "size": len(pdf_content),
        "base64": True,
    }

    # Create a webhook payload with the expected WebhookData format
    payload = {
        "webhook_id": f"test-webhook-{int(time.time())}",
        "event": "inbound_email",
        "timestamp": datetime.utcnow().isoformat(),
        "data": {
            "message_id": f"test-message-{int(time.time())}@example.com",
            "from_email": "test@example.com",
            "from_name": "Test Sender",
            "to_email": "recipient@example.com",
            "subject": "Test Email with PDF Attachment",
            "body_plain": "This is a test email with a PDF attachment.",
            "body_html": "<p>This is a test email with a PDF attachment.</p>",
            "headers": {
                "From": "Test Sender <test@example.com>",
                "To": "recipient@example.com",
                "Subject": "Test Email with PDF Attachment",
            },
            "attachments": [attachment],
        },
    }

    return payload


async def simulate_webhook_processing(webhook_payload: Dict[str, Any]) -> Email:
    """Process a webhook payload through the system.

    Args:
        webhook_payload: The webhook payload to process

    Returns:
        Email: The created Email model instance
    """
    # Create a database session
    async with async_session_factory() as db:
        # Create needed services
        storage_service = StorageService()
        attachment_service = AttachmentService(db, storage_service)
        email_service = EmailService(db, attachment_service, storage_service)

        # Convert dictionary to MailchimpWebhook for type safety
        webhook_model = MailchimpWebhook(
            webhook_id=webhook_payload["webhook_id"],
            event=webhook_payload["event"],
            timestamp=datetime.fromisoformat(webhook_payload["timestamp"]),
            data=webhook_payload["data"],
        )

        # Extract data as a schema before processing
        if isinstance(webhook_model.data, dict):
            # Handle dictionary data from the payload
            schema_data = InboundEmailData(**webhook_model.data)
        else:
            # It's already an InboundEmailData object
            schema_data = InboundEmailData(**webhook_model.data.model_dump())

        # Create the webhook data schema
        schema_webhook = WebhookData(
            webhook_id=webhook_model.webhook_id or "",
            event=webhook_model.event or "",
            timestamp=webhook_model.timestamp or datetime.utcnow(),
            data=schema_data,
        )

        # Process the webhook (this will save the email and attachments to the database)
        logger.info("Processing webhook...")
        email = await email_service.process_webhook(schema_webhook)
        logger.info(f"Email processed and saved with ID: {email.id}")

        return email


async def wait_for_ocr_completion(
    email_id: int, timeout: int = 60
) -> List[AttachmentTextContent]:
    """Wait for OCR to complete and return the extracted text content.

    Args:
        email_id: The ID of the email to check
        timeout: Maximum time to wait in seconds

    Returns:
        List[AttachmentTextContent]: The extracted text content records
    """
    start_time = time.time()
    ocr_results = []

    # Create a database session
    async with async_session_factory() as db:
        while time.time() - start_time < timeout:
            # Get the attachments for this email
            query = select(Attachment).where(Attachment.email_id == email_id)
            result = await db.execute(query)
            attachments = result.scalars().all()

            if not attachments:
                logger.warning(f"No attachments found for email ID: {email_id}")
                return []

            # For each attachment, check if OCR has completed
            all_completed = True
            for attachment in attachments:
                # Query for OCR content
                ocr_query = select(AttachmentTextContent).where(
                    AttachmentTextContent.attachment_id == attachment.id
                )
                ocr_result = await db.execute(ocr_query)
                ocr_content = ocr_result.scalars().all()

                if not ocr_content:
                    logger.info(
                        f"OCR still in progress for attachment ID: {attachment.id}..."
                    )
                    all_completed = False
                    break

                ocr_results = ocr_content

            if all_completed and ocr_results:
                logger.info(
                    f"OCR completed for all attachments of email ID: {email_id}"
                )
                return ocr_results

            # Wait before checking again
            await asyncio.sleep(2)

    logger.warning(f"Timeout waiting for OCR completion for email ID: {email_id}")
    return ocr_results


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


async def monitor_redis_activity(task_id: Optional[str] = None) -> None:
    """Monitor and print Redis activity related to the OCR task.

    Args:
        task_id: Optional specific task ID to monitor
    """
    redis = RedisService()

    print("\n📊 Redis Activity:")
    print("================")

    # If we have a specific task ID, show its status
    if task_id:
        task_key = f"celery-task-meta-{task_id}"
        task_status = redis.get(task_key)

        if task_status:
            print(f"Task {task_id} status: {task_status}")
        else:
            print(f"No status found for task {task_id}")


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
        # Step 1: Create test webhook payload
        print("\n📧 Creating test email with PDF attachment...")
        webhook_payload = create_test_webhook_payload(SAMPLE_PDF_PATH)

        # Step 2: Process the webhook (simulates receiving an email)
        print("\n🔄 Processing email webhook...")
        email = await simulate_webhook_processing(webhook_payload)
        print(f"✅ Email processed successfully (ID: {email.id})")

        # Step 3: Wait for OCR to complete
        print("\n⏳ Waiting for OCR to complete...")
        ocr_results = await wait_for_ocr_completion(email.id)

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
