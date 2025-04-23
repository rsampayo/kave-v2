"""Celery tasks for asynchronous processing.

This module will contain task definitions for PDF OCR processing.
"""

import logging
from typing import Any, cast

from asgiref.sync import async_to_sync
from celery import shared_task  # type: ignore
from celery.exceptions import MaxRetriesExceededError, Retry  # type: ignore

from app.core.config import settings  # noqa: F401 - Will be used in future steps
from app.db.session import get_session
from app.models.email_data import Attachment
from app.services.storage_service import StorageService

logger = logging.getLogger(__name__)


@shared_task(  # type: ignore
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name="app.worker.tasks.process_pdf_attachment",
)
def process_pdf_attachment(self: Any, attachment_id: int) -> str:  # noqa: C901
    """
    Celery task to OCR a PDF attachment page by page.

    Args:
        self: The task instance (automatically passed with bind=True).
        attachment_id: The ID of the Attachment record to process.

    Returns:
        A status message string.
    """
    task_id = cast(str, self.request.id)
    logger.info(
        f"Task {task_id}: Starting OCR process for attachment ID: {attachment_id}"
    )

    db = None  # Initialize db to None for finally block safety
    try:
        # Get a SYNC session
        db = get_session()

        # 1. Fetch Attachment metadata
        attachment = db.get(Attachment, attachment_id)
        if not attachment:
            logger.error(f"Task {task_id}: Attachment {attachment_id} not found.")
            return f"Task {task_id}: Attachment {attachment_id} not found."
        if not attachment.storage_uri:
            logger.error(
                f"Task {task_id}: Attachment {attachment_id} has no storage URI."
            )
            return f"Task {task_id}: Attachment {attachment_id} has no storage URI."

        logger.info(
            f"Task {task_id}: Found attachment {attachment_id} with URI: {attachment.storage_uri}"
        )

        # 2. Retrieve PDF content from storage (bridging sync task to async storage)
        storage = StorageService()
        try:
            # Use async_to_sync to bridge sync (task) to async (storage)
            pdf_data = async_to_sync(storage.get_file)(attachment.storage_uri)
        except Exception as storage_err:
            storage_uri = attachment.storage_uri
            logger.error(
                f"Task {task_id}: Failed to get PDF from storage {storage_uri}: {storage_err}"
            )
            raise  # Re-raise to potentially trigger retry

        if not pdf_data:
            logger.error(
                f"Task {task_id}: Could not retrieve PDF data from {attachment.storage_uri}"
            )
            # Consider retrying if this might be transient
            uri_msg = f"PDF data not found at {attachment.storage_uri}"
            raise self.retry(exc=Exception(uri_msg), countdown=60)

        logger.info(
            f"Task {task_id}: Successfully retrieved PDF data ({len(pdf_data)} bytes) "
            f"for attachment {attachment_id}"
        )

        # --- PDF processing logic (Next Steps) ---
        # Placeholder success return for this step
        return (
            f"Task {task_id}: Successfully fetched data for attachment {attachment_id}"
        )

    except Retry:
        # Important: Re-raise Retry exceptions to let Celery handle them
        raise
    except Exception as e:
        logger.error(
            f"Task {task_id}: Error processing attachment {attachment_id}: {e}",
            exc_info=True,
        )
        # Rollback not needed yet
        try:
            # Retry the task with exponential backoff
            logger.warning(
                f"Task {task_id}: Retrying task for attachment {attachment_id} due to error: {e}"
            )
            # Ensure exc is passed for Celery >= 5
            raise self.retry(
                exc=e, countdown=int(60 * (self.request.retries + 1))
            ) from e
        except MaxRetriesExceededError:
            logger.error(
                f"Task {task_id}: Max retries exceeded for attachment {attachment_id}. Giving up."
            )
            return (
                f"Task {task_id}: Failed attachment {attachment_id} after max retries."
            )
        except Retry:
            # Re-raise if self.retry itself raises Retry
            raise
        except Exception as retry_err:
            logger.error(
                f"Task {task_id}: Failed to enqueue retry for task {attachment_id}: {retry_err}"
            )
            # Use proper error handling - can't use "from" with return statements
            logger.error(f"Original error: {e}")
            return (
                f"Task {task_id}: Failed attachment {attachment_id}, could not retry."
            )
    finally:
        if db:
            # TrackedAsyncSession.close() is async, we need to use async_to_sync
            async_to_sync(db.close)()
            logger.debug(
                f"Task {task_id}: Database session closed for attachment {attachment_id}"
            )
