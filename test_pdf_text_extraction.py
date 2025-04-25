#!/usr/bin/env python3
"""Test script for PDF text extraction and storage.

This script tests if PDF text extraction works properly by:
1. Creating a sample PDF with known text content
2. Sending a test email with this PDF attachment via the API
3. Checking the database to verify the extracted text is stored correctly
"""

import asyncio
import base64
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import psycopg2
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

# Import app's configuration to use the same database
from app.core.config import settings

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Constants
API_URL = "http://localhost:8000"  # Assuming the app is running locally on port 8000
WEBHOOK_ENDPOINT = "/v1/webhooks/mandrill"  # Correct webhook endpoint
WAIT_TIMEOUT = 60  # Wait timeout in seconds for PDF processing

# Get the database URL from app settings
DB_URL = settings.effective_database_url
logger.info(f"Using database: {DB_URL}")


def create_test_pdf(output_path: Path) -> Path:
    """Create a sample PDF file with specific text for testing text extraction.

    Args:
        output_path: Path where the PDF will be saved

    Returns:
        Path: Path to the created PDF file
    """
    # Create the parent directory if it doesn't exist
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Create a PDF with reportlab
    c = canvas.Canvas(str(output_path), pagesize=letter)

    # Add content to multiple pages with specific text to verify extraction
    for page in range(1, 4):  # Create 3 pages
        c.setFont("Helvetica", 12)
        c.drawString(100, 750, f"Text Extraction Test - Page {page}")
        c.drawString(100, 730, f"UNIQUE_TEST_IDENTIFIER_PAGE_{page}")
        c.drawString(100, 710, f"This is test content for page {page}")
        c.drawString(
            100, 690, "This text should be extracted and saved in the database."
        )
        c.drawString(
            100, 670, "Lorem ipsum dolor sit amet, consectetur adipiscing elit."
        )
        c.drawString(
            100,
            650,
            f"Page {page} test content with timestamp: {datetime.now().isoformat()}",
        )

        # Add page number at the bottom
        c.setFont("Helvetica", 8)
        c.drawString(280, 50, f"Page {page} of 3")

        if page < 3:  # Don't add a new page after the last page
            c.showPage()

    # Save the PDF
    c.save()
    logger.info(f"Test PDF created at: {output_path}")
    return output_path


def create_mandrill_webhook_payload(pdf_path: Path) -> Dict[str, Any]:
    """Create a Mandrill webhook payload with the PDF attachment.

    Args:
        pdf_path: Path to the PDF file

    Returns:
        Dict: Webhook payload in Mandrill format
    """
    # Read the PDF file
    with open(pdf_path, "rb") as f:
        pdf_content = f.read()

    # Create a unique message ID and timestamp
    message_id = f"test-extraction-{int(time.time())}@example.com"
    timestamp = datetime.utcnow().isoformat()

    # Create the attachment data in Mandrill format
    attachment = {
        "name": "text-extraction-test.pdf",
        "type": "application/pdf",
        "content": base64.b64encode(pdf_content).decode("utf-8"),
        "size": len(pdf_content),
        "base64": True,
    }

    # Create the webhook payload in the format our endpoint expects
    # The server is expecting this specific format with a 'data' field
    payload = {
        "webhook_id": f"test-webhook-{int(time.time())}",
        "event": "inbound_email",
        "timestamp": timestamp,
        "data": {
            "message_id": message_id,
            "from_email": "test@example.com",
            "from_name": "PDF Extraction Test",
            "to_email": "recipient@example.com",
            "subject": "PDF Text Extraction Test",
            "body_plain": "This email contains a PDF attachment for testing text extraction.",
            "body_html": "<p>This email contains a PDF attachment for testing text extraction.</p>",
            "headers": {
                "Message-ID": message_id,
                "From": "PDF Extraction Test <test@example.com>",
                "To": "recipient@example.com",
                "Subject": "PDF Text Extraction Test",
                "Date": timestamp,
                "Content-Type": "multipart/mixed",
            },
            "attachments": [attachment],
        },
    }

    return payload


async def send_webhook(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Send the webhook to the API endpoint.

    Args:
        payload: Webhook payload

    Returns:
        Dict: API response
    """
    webhook_url = f"{API_URL}{WEBHOOK_ENDPOINT}"

    async with httpx.AsyncClient() as client:
        logger.info(f"Sending webhook to {webhook_url}")
        response = await client.post(
            webhook_url,
            json=payload,
            headers={
                "Content-Type": "application/json",
                # No signature for now, relying on development mode for acceptance
            },
            timeout=30.0,
        )

        # Log the status code
        logger.info(f"Response status code: {response.status_code}")

        if response.status_code >= 400:
            logger.error(f"Error response: {response.text}")
            raise Exception(f"API request failed with status {response.status_code}")

        try:
            return response.json()
        except json.JSONDecodeError:
            return {"status": "success", "data": response.text}


def check_for_active_workers() -> bool:
    """Check if Celery workers are active.

    Returns:
        bool: True if active workers found, False otherwise
    """
    try:
        import subprocess

        # Use ps command to check for running celery workers
        result = subprocess.run(
            ["ps", "aux"], capture_output=True, text=True, timeout=5
        )

        if (
            "celery" in result.stdout
            and "app.worker.celery_app worker" in result.stdout
        ):
            logger.info("Celery workers are active")
            return True
        else:
            logger.warning(
                "No active Celery workers found. PDF processing might not work."
            )
            return False

    except Exception as e:
        logger.warning(f"Could not check Celery worker status: {e}")
        return False


def get_db_connection():
    """Get a database connection to the PostgreSQL database.

    Returns:
        Connection object: PostgreSQL connection
    """
    # Parse the PostgreSQL URL
    # Format: postgresql://username:password@host:port/dbname
    parsed_url = DB_URL.replace("postgresql://", "").split("/")
    dbname = parsed_url[-1]
    credentials_host = parsed_url[0].split("@")
    host = (
        credentials_host[-1].split(":")[0]
        if ":" in credentials_host[-1]
        else credentials_host[-1]
    )
    port = credentials_host[-1].split(":")[1] if ":" in credentials_host[-1] else "5432"

    if "@" in parsed_url[0]:
        credentials = credentials_host[0].split(":")
        username = credentials[0]
        password = credentials[1] if len(credentials) > 1 else ""
    else:
        username = ""
        password = ""

    # Connect to PostgreSQL
    logger.debug(
        f"Connecting to PostgreSQL: host={host}, port={port}, dbname={dbname}, user={username}"
    )
    return psycopg2.connect(
        dbname=dbname, user=username, password=password, host=host, port=port
    )


def check_database_setup() -> bool:
    """Check if the database has the necessary tables for PDF text extraction.

    Returns:
        bool: True if the database is properly set up, False otherwise
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if attachment_text_content table exists in PostgreSQL
        cursor.execute(
            "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name='attachment_text_content')"
        )
        table_exists = cursor.fetchone()[0]

        if not table_exists:
            logger.error(
                "The 'attachment_text_content' table doesn't exist in the database."
            )
            logger.error("Please run database migrations to create this table:")
            logger.error("alembic upgrade head")
            return False

        return True

    except Exception as e:
        logger.error(f"Error checking database setup: {e}")
        return False

    finally:
        if conn:
            conn.close()


def check_redis_connectivity() -> bool:
    """Check if Redis is accessible.

    Returns:
        bool: True if Redis is accessible, False otherwise
    """
    try:
        import redis

        from app.core.config import settings

        # Use the same Redis URL as Celery broker if available
        redis_url = settings.REDIS_URL or settings.CELERY_BROKER_URL

        # Create a Redis client and try to ping
        client = redis.Redis.from_url(redis_url)
        return client.ping()
    except Exception as e:
        logger.error(f"Redis connectivity check failed: {e}")
        return False


def manually_enqueue_pdf_processing(attachment_id: int) -> bool:
    """Manually enqueue PDF processing for an attachment using Celery only.

    Args:
        attachment_id: ID of the attachment to process

    Returns:
        bool: True if successful, False otherwise
    """
    # First check Redis connectivity
    if not check_redis_connectivity():
        logger.error("Cannot enqueue PDF processing: Redis is not accessible")
        return False

    try:
        # Import the task directly
        from app.worker.celery_app import celery_app
        from app.worker.tasks import process_pdf_attachment

        # Send the task using the Celery app instance
        logger.info(
            f"Enqueueing attachment {attachment_id} for processing using Celery task"
        )
        result = process_pdf_attachment.delay(attachment_id)

        # Log task ID for reference
        logger.info(f"Celery task {result.id} created for attachment {attachment_id}")

        # Add a short delay to give the worker time to pick up the task
        time.sleep(2)

        return True
    except Exception as e:
        logger.error(f"Error enqueuing PDF processing via Celery: {e}")
        return False


def get_latest_email_id() -> int:
    """Get the ID of the most recently processed email from the database.

    Returns:
        int: Email ID
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM emails ORDER BY id DESC LIMIT 1")
        result = cursor.fetchone()
        if result:
            return result[0]
        return None
    except Exception as e:
        logger.error(f"Error getting latest email ID: {e}")
        return None
    finally:
        if conn:
            conn.close()


def check_attachment_text_content(email_id: int) -> bool:
    """Check if text has been extracted and saved for the email's PDF attachment.

    Args:
        email_id: ID of the email

    Returns:
        bool: True if text was found, False otherwise
    """
    # First, check if the database has the necessary structure
    if not check_database_setup():
        logger.error("Database is not properly set up for PDF text extraction")
        return False

    conn = None
    attachment_id = None

    try:
        # Connect to the database
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get the attachment ID for this email
        cursor.execute("SELECT id FROM attachments WHERE email_id = %s", (email_id,))
        attachment_result = cursor.fetchone()

        if not attachment_result:
            logger.error(f"No attachment found for email {email_id}")
            return False

        attachment_id = attachment_result[0]
        logger.info(f"Found attachment with ID: {attachment_id}")

        # Check storage URI and content type
        cursor.execute(
            "SELECT storage_uri, content_type FROM attachments WHERE id = %s",
            (attachment_id,),
        )
        storage_info = cursor.fetchone()
        if storage_info:
            logger.info(
                f"Attachment storage URI: {storage_info[0]}, Content-Type: {storage_info[1]}"
            )

        # Manually trigger PDF processing via Celery
        logger.info(
            f"Manually triggering PDF processing for attachment {attachment_id} via Celery"
        )
        manually_enqueue_pdf_processing(attachment_id)

        # Wait for text content to appear with a timeout
        start_time = time.time()
        logger.info(
            f"Waiting up to {WAIT_TIMEOUT} seconds for text extraction to complete..."
        )

        while time.time() - start_time < WAIT_TIMEOUT:
            # Check for text content entries
            cursor.execute(
                "SELECT page_number, text_content FROM attachment_text_content WHERE attachment_id = %s ORDER BY page_number",
                (attachment_id,),
            )
            text_content_results = cursor.fetchall()

            if text_content_results:
                # Text content found!
                logger.info(
                    f"Found {len(text_content_results)} pages of text content for attachment {attachment_id}"
                )

                # Verify the content contains our markers
                success = True
                for page_number, text_content in text_content_results:
                    expected_marker = f"UNIQUE_TEST_IDENTIFIER_PAGE_{page_number}"
                    if text_content and expected_marker in text_content:
                        logger.info(
                            f"✅ Page {page_number}: Found expected marker '{expected_marker}'"
                        )
                        # Print a preview of the text
                        preview = (
                            text_content[:100] + "..."
                            if len(text_content) > 100
                            else text_content
                        )
                        logger.info(f"Preview: {preview}")
                    else:
                        logger.error(
                            f"❌ Page {page_number}: Missing expected marker '{expected_marker}'"
                        )
                        success = False

                return success

            # Wait 5 seconds before checking again
            logger.info("No text content found yet, waiting 5 seconds...")
            time.sleep(5)

        logger.error(
            f"Timeout reached after {WAIT_TIMEOUT} seconds. No text content found."
        )
        return False

    except Exception as e:
        logger.error(f"Error checking for text content: {e}")
        return False

    finally:
        if conn:
            conn.close()


def purge_celery_tasks() -> bool:
    """Purge all pending Celery tasks and clear related Redis keys.

    Returns:
        bool: True if successful, False otherwise
    """
    success = True

    try:
        from app.worker.celery_app import celery_app

        logger.info("Purging all pending Celery tasks...")
        celery_app.control.purge()

        # Additional step: Cancel any running/reserved tasks
        inspected = celery_app.control.inspect()

        # Get all active, reserved, and scheduled tasks
        active_tasks = inspected.active() or {}
        reserved_tasks = inspected.reserved() or {}
        scheduled_tasks = inspected.scheduled() or {}

        # Flatten into a list of task IDs
        all_tasks = []
        for worker, tasks in active_tasks.items():
            all_tasks.extend(task["id"] for task in tasks)
        for worker, tasks in reserved_tasks.items():
            all_tasks.extend(task["id"] for task in tasks)
        for worker, tasks in scheduled_tasks.items():
            all_tasks.extend(task["id"] for task in tasks)

        # Revoke tasks with terminate=True to force stop them
        if all_tasks:
            logger.info(f"Revoking {len(all_tasks)} active/reserved/scheduled tasks...")
            celery_app.control.revoke(all_tasks, terminate=True)

        logger.info("Celery task queue purged successfully")

        # Clear Redis keys related to Celery
        try:
            import redis

            from app.core.config import settings

            redis_url = settings.REDIS_URL or settings.CELERY_BROKER_URL
            redis_client = redis.Redis.from_url(redis_url)

            # Clear Celery-specific keys in Redis
            celery_keys = redis_client.keys("celery*")
            if celery_keys:
                logger.info(f"Clearing {len(celery_keys)} Celery-related Redis keys...")
                redis_client.delete(*celery_keys)

            # Additional Redis cleanup specifically for task results
            task_result_keys = redis_client.keys("_kombu*") + redis_client.keys(
                "unacked*"
            )
            if task_result_keys:
                logger.info(f"Clearing {len(task_result_keys)} task result keys...")
                for key in task_result_keys:
                    redis_client.delete(key)

            logger.info("Redis Celery keys cleared successfully")
        except Exception as e:
            logger.error(f"Error clearing Redis keys: {e}")
            success = False

    except Exception as e:
        logger.error(f"Error purging Celery tasks: {e}")
        success = False

    return success


async def main() -> None:
    """Run the PDF text extraction test."""
    print("\n📄 PDF Text Extraction Test")
    print("=========================")
    print(f"Using database: {DB_URL}")

    # Purge Celery tasks and clear Redis keys before running the test
    print("\n🧹 Purging pending Celery tasks and Redis keys...")
    if purge_celery_tasks():
        print("✅ Celery tasks and Redis keys purged successfully")
    else:
        print(
            "⚠️ Could not fully purge Celery tasks and Redis keys, continuing anyway..."
        )
        print("   You may want to restart Celery workers before continuing.")
        response = input("Continue with test? (y/n): ")
        if response.lower() != "y":
            print("Test aborted.")
            return

    # Check database setup
    print("\n🔍 Checking database setup...")
    if not check_database_setup():
        print("❌ Database is not properly set up for PDF text extraction")
        print("\nPlease run the following commands to set up the database:")
        print("1. cd /Users/rsampayo/Documents/Proyectos/Kave")
        print("2. alembic upgrade head")
        print("\nAfter migration is complete, run this test again.")
        return

    # Check if celery workers are running
    print("\n🔍 Checking for Celery workers...")
    workers_active = check_for_active_workers()
    if not workers_active:
        print("❌ No active Celery workers found. PDF processing will not work.")
        print("Please run: celery --app app.worker.celery_app worker --loglevel=info")
        print("Then try running this test again.")
        return

    # Check Redis connectivity
    print("\n🔍 Checking Redis connectivity...")
    redis_accessible = check_redis_connectivity()
    if not redis_accessible:
        print(
            "❌ Redis is not accessible. Make sure Redis is running on the configured URL."
        )
        print(f"   Using Redis URL: {settings.REDIS_URL or settings.CELERY_BROKER_URL}")
        print("   Try running: redis-cli ping")
        return
    else:
        print("✅ Redis is accessible")

    # Create a temp directory for the test PDF
    temp_dir = Path("./test_data")
    temp_dir.mkdir(exist_ok=True)
    test_pdf_path = temp_dir / "text_extraction_test.pdf"

    try:
        # Step 1: Create the test PDF
        print("\n📝 Creating test PDF with specific text content...")
        create_test_pdf(test_pdf_path)

        # Step 2: Create and send the webhook
        print("\n📧 Creating Mandrill webhook payload with PDF attachment...")
        payload = create_mandrill_webhook_payload(test_pdf_path)

        print("\n🔄 Sending webhook to API...")
        response = await send_webhook(payload)
        print(f"✅ Webhook sent successfully: {response}")

        # Step 3: Get the latest email ID
        print("\n🔍 Getting email ID from database...")
        email_id = get_latest_email_id()
        if not email_id:
            print("❌ Could not find the email ID in the database. Test failed.")
            return

        print(f"✅ Found email ID: {email_id}")

        # Step 4: Check for text extraction - now with single check and longer timeout
        print(
            f"\n⏳ Waiting up to {WAIT_TIMEOUT} seconds for text extraction to complete..."
        )
        success = check_attachment_text_content(email_id)

        if success:
            print("\n✨ PDF text extraction test passed successfully!")
            print(
                "✅ Text was correctly extracted from the PDF and saved in the database"
            )
        else:
            print(
                "\n❌ PDF text extraction test failed - text was not correctly extracted or saved"
            )
            print("\nTroubleshooting tips:")
            print(
                "1. Make sure Celery workers are running: celery --app app.worker.celery_app worker --loglevel=info"
            )
            print("2. Check server logs for error messages")
            print(
                "3. Verify that the webhook endpoint is processing attachments correctly"
            )
            print("4. Check that the PDF processing task is being triggered in Celery")
            print(
                "5. Ensure the database tables are created with 'alembic upgrade head'"
            )
            print("6. Verify Redis is running: redis-cli ping")
            print(
                f"7. Check Redis connection settings: {settings.REDIS_URL or settings.CELERY_BROKER_URL}"
            )

    except Exception as e:
        logger.exception("Error in PDF text extraction test")
        print(f"\n❌ Test failed with error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
