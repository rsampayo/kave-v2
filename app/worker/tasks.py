"""Celery tasks for asynchronous processing.

This module will contain task definitions for PDF OCR processing.
"""

import logging
from typing import Any, cast

import fitz  # type: ignore[import-untyped]
from asgiref.sync import async_to_sync
from celery import shared_task  # type: ignore
from celery.exceptions import MaxRetriesExceededError, Retry  # type: ignore

from app.core.config import settings  # noqa: F401 - Will be used in future steps
from app.db.session import get_session
from app.models.attachment_text_content import AttachmentTextContent
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

        # Open the PDF with PyMuPDF
        try:
            doc = fitz.open(stream=pdf_data, filetype="pdf")
            logger.info(
                f"Task {task_id}: Opened PDF for attachment {attachment_id}. "
                f"Page count: {doc.page_count}"
            )
        except Exception as pdf_err:
            logger.error(
                f"Task {task_id}: Failed to open PDF for attachment {attachment_id}: "
                f"{pdf_err}"
            )
            # Decide if this is retryable. Corrupt PDF likely isn't.
            # For now, we'll just return failure status. Could retry if it might be transient.
            return f"Task {task_id}: Failed to open PDF for attachment {attachment_id}"

        # Initialize counters
        total_pages = doc.page_count
        processed_pages = 0
        errors_on_pages = 0
        page_commit_counter = 0

        def check_error_threshold() -> None:
            """Check if the error percentage exceeds the configured threshold.

            Raises:
                ValueError: If error percentage exceeds threshold.
            """
            if errors_on_pages > 0:
                error_percentage = (errors_on_pages / total_pages) * 100
                if error_percentage > settings.PDF_MAX_ERROR_PERCENTAGE:
                    logger.error(
                        f"Task {task_id}: Error threshold exceeded "
                        f"({error_percentage:.1f}% > {settings.PDF_MAX_ERROR_PERCENTAGE}%). "
                        f"Failing task after {errors_on_pages}/{total_pages} page errors."
                    )
                    raise ValueError(
                        f"Too many page errors ({errors_on_pages}/{total_pages} pages failed)"
                    )

        # Determine transaction strategy
        if settings.PDF_USE_SINGLE_TRANSACTION:
            # Process entire PDF in a single transaction
            with db.begin():
                for page_num in range(total_pages):
                    try:
                        page = doc.load_page(page_num)
                        # Direct text extraction
                        page_text = (
                            page.get_text("text") or ""
                        )  # Default to empty string if None

                        # Create and Save AttachmentTextContent record
                        text_content_entry = AttachmentTextContent(
                            attachment_id=attachment_id,
                            page_number=page_num + 1,  # Page numbers are 1-based
                            text_content=page_text.strip() if page_text else None,
                        )
                        db.add(text_content_entry)
                        processed_pages += 1
                        logger.debug(
                            f"Task {task_id}: Added page {page_num + 1}/{total_pages} "
                            f"content for attachment {attachment_id}"
                        )

                    except Exception as page_err:
                        errors_on_pages += 1
                        logger.error(
                            f"Task {task_id}: Error processing page {page_num + 1} "
                            f"for attachment {attachment_id}: {page_err}"
                        )
                        check_error_threshold()  # May raise ValueError if too many errors
                        # Continue to next page if within error threshold

        else:
            # Process PDF with periodic commits
            for page_num in range(total_pages):
                try:
                    page = doc.load_page(page_num)
                    # Direct text extraction
                    page_text = (
                        page.get_text("text") or ""
                    )  # Default to empty string if None

                    # Create and Save AttachmentTextContent record
                    text_content_entry = AttachmentTextContent(
                        attachment_id=attachment_id,
                        page_number=page_num + 1,  # Page numbers are 1-based
                        text_content=page_text.strip() if page_text else None,
                    )
                    db.add(text_content_entry)
                    page_commit_counter += 1
                    processed_pages += 1
                    logger.debug(
                        f"Task {task_id}: Added page {page_num + 1}/{total_pages} "
                        f"content for attachment {attachment_id}"
                    )

                    # Commit periodically if batch size is set
                    if (
                        settings.PDF_BATCH_COMMIT_SIZE > 0
                        and page_commit_counter >= settings.PDF_BATCH_COMMIT_SIZE
                    ):
                        # Use async_to_sync for db.commit()
                        async_to_sync(db.commit)()
                        logger.info(
                            f"Task {task_id}: Committed batch of {page_commit_counter} "
                            f"pages for attachment {attachment_id}"
                        )
                        page_commit_counter = 0

                except Exception as page_err:
                    errors_on_pages += 1
                    logger.error(
                        f"Task {task_id}: Error processing page {page_num + 1} "
                        f"for attachment {attachment_id}: {page_err}"
                    )
                    # Use async_to_sync for db.rollback()
                    async_to_sync(db.rollback)()  # Rollback current batch on page error
                    page_commit_counter = 0  # Reset counter after rollback
                    check_error_threshold()  # May raise ValueError if too many errors
                    # Continue to next page if within error threshold

            # Commit any remaining entries after the loop
            if page_commit_counter > 0:
                # Use async_to_sync for db.commit()
                async_to_sync(db.commit)()
                logger.info(
                    f"Task {task_id}: Committed final batch of {page_commit_counter} "
                    f"pages for attachment {attachment_id}"
                )

        # Final status message
        status_msg = (
            f"Task {task_id}: Attachment {attachment_id} processed. "
            f"Pages: {total_pages}, Success: {processed_pages}, Errors: {errors_on_pages}."
        )
        logger.info(status_msg)

        # Log warning if there were any errors (but below threshold)
        if errors_on_pages > 0:
            logger.warning(
                f"Task {task_id}: Finished processing attachment {attachment_id} "
                f"with {errors_on_pages} page errors "
                f"({(errors_on_pages/total_pages)*100:.1f}% error rate)."
            )

        return status_msg  # Return detailed status

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
