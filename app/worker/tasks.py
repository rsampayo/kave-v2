"""Celery tasks for asynchronous processing.

This module will contain task definitions for PDF OCR processing.
"""

import io
import logging
from typing import Any, cast

import fitz  # type: ignore[import-untyped]
import pytesseract  # type: ignore[import-untyped]
from asgiref.sync import async_to_sync
from celery import shared_task  # type: ignore
from celery.exceptions import MaxRetriesExceededError, Retry  # type: ignore
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.session import get_session
from app.models.attachment_text_content import AttachmentTextContent
from app.models.email_data import Attachment
from app.services.storage_service import StorageService

logger = logging.getLogger(__name__)


def sync_db_operation(db: Any, operation: str, *args: Any, **kwargs: Any) -> Any:
    """Execute database operation synchronously.
    
    This function safely bridges async database operations to sync context.
    
    Args:
        db: Database session
        operation: The operation to perform ('commit', 'rollback', 'close', 'add', 'get')
        args: Arguments to pass to the operation
        kwargs: Keyword arguments to pass to the operation
        
    Returns:
        Any: Result of the operation if any
    """
    try:
        if operation == 'commit':
            try:
                # Create a proper async function to handle commit
                async def do_commit():
                    try:
                        await db.commit()
                        return True
                    except Exception as e:
                        logger.error(f"Error in async commit: {e}")
                        raise
                
                # Execute the commit in a new thread
                result = async_to_sync(do_commit)()
                
                # Reset transaction state after commit to prevent "another operation in progress" errors
                async def reset_session():
                    if hasattr(db, 'close'):
                        try:
                            # Close any lingering transactions
                            await db.close()
                        except Exception:
                            pass
                    # Get a fresh transaction state
                    if hasattr(db, 'begin'):
                        try:
                            await db.begin()
                        except Exception:
                            pass
                    return True
                
                # Ensure session is in a clean state
                async_to_sync(reset_session)()
                
                return result
            except Exception as commit_err:
                logger.error(f"Commit error: {commit_err}, attempting to rollback")
                try:
                    # Create proper async function for rollback
                    async def do_rollback():
                        try:
                            await db.rollback()
                            return True
                        except Exception as e:
                            logger.error(f"Error in async rollback: {e}")
                            # Just suppress errors here to allow for a clean abort
                            return False
                    
                    async_to_sync(do_rollback)()
                except Exception:
                    # If rollback fails, we have to close and discard the session
                    pass
                raise
        elif operation == 'rollback':
            try:
                # Create proper async function for rollback
                async def do_rollback():
                    try:
                        await db.rollback()
                        return True
                    except Exception as e:
                        logger.error(f"Error in async rollback: {e}")
                        return False
                
                result = async_to_sync(do_rollback)()
                
                # Reset transaction state after rollback
                async def reset_session():
                    if hasattr(db, 'close'):
                        try:
                            await db.close()
                        except Exception:
                            pass
                    # Get a fresh transaction state
                    if hasattr(db, 'begin'):
                        try:
                            await db.begin()
                        except Exception:
                            pass
                    return True
                
                # Ensure session is in a clean state
                async_to_sync(reset_session)()
                
                return result
            except Exception as rollback_err:
                logger.error(f"Rollback error: {rollback_err}, will close session")
                raise
        elif operation == 'close':
            try:
                # Create proper async function for close
                async def do_close():
                    try:
                        await db.close()
                        return True
                    except Exception as e:
                        logger.error(f"Error in async close: {e}")
                        return False
                
                return async_to_sync(do_close)()
            except Exception as close_err:
                logger.error(f"Close error: {close_err}")
                raise
        elif operation == 'add':
            db.add(*args)
            return None
        elif operation == 'get':
            try:
                # Instead of using a new transaction, use the raw connection directly 
                # to avoid transaction nesting issues
                entity_class = args[0]
                entity_id = args[1]
                stmt = select(entity_class).where(entity_class.id == entity_id)
                
                async def get_entity():
                    try:
                        # Execute directly without transaction management
                        raw_conn = await db.connection()
                        result = await raw_conn.execute(stmt)
                        # Make sure we're getting the full entity object, not just the ID
                        entity = result.scalar_one_or_none()
                        logger.debug(f"Got entity type: {type(entity)} for ID: {entity_id}")
                        return entity
                    except Exception as e:
                        logger.error(f"Error in async execute/scalar: {e}")
                        raise
                    
                return async_to_sync(get_entity)()
            except Exception as get_err:
                logger.error(f"Get error: {get_err}")
                raise
        else:
            raise ValueError(f"Unsupported operation: {operation}")
    except Exception as e:
        logger.error(f"Error in sync_db_operation '{operation}': {e}")
        raise


@shared_task(  # type: ignore
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name="app.worker.tasks.process_pdf_attachment",
)
def process_pdf_attachment(self: Any, attachment_id: int) -> str:  # noqa: C901
    """
    Celery task to extract text from PDF attachments using PyMuPDF with Tesseract OCR fallback.

    The task performs the following steps:
    1. Retrieves the Attachment record and its PDF data from storage
    2. Opens the PDF using PyMuPDF
    3. Processes each page:
       - Attempts direct text extraction via PyMuPDF
       - If minimal text is found, falls back to Tesseract OCR
    4. Saves extracted text per page to AttachmentTextContent records

    Transaction handling is configurable:
    - Single transaction per PDF (PDF_USE_SINGLE_TRANSACTION=True)
    - Batched commits (PDF_BATCH_COMMIT_SIZE > 0)

    Error handling includes:
    - Retries for transient failures
    - Error threshold monitoring (fails if PDF_MAX_ERROR_PERCENTAGE exceeded)
    - Graceful fallback to direct text if OCR fails

    Args:
        self: Task instance (Celery bind=True).
        attachment_id: ID of the Attachment record to process.

    Returns:
        str: Status message describing the processing outcome.

    Raises:
        Retry: For transient errors that should trigger a retry.
        ValueError: If error threshold is exceeded.
    """
    task_id = cast(str, self.request.id)
    logger.info(
        f"Task {task_id}: Starting OCR process for attachment ID: {attachment_id}"
    )

    db = None  # Initialize db to None for finally block safety
    try:
        # Get a sync session
        engine = create_engine(settings.effective_database_url)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        
        # Create the session
        db_session = SessionLocal()
        
        # Fetch Attachment metadata using synchronous session
        try:
            stmt = select(Attachment).where(Attachment.id == attachment_id)
            attachment = db_session.execute(stmt).scalar_one_or_none()
            
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
        except Exception as fetch_err:
            logger.error(f"Task {task_id}: Failed to fetch attachment: {fetch_err}")
            raise self.retry(exc=fetch_err, countdown=30)

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

        # Clean up existing text content
        try:
            # Delete any existing text content for this attachment
            delete_stmt = AttachmentTextContent.__table__.delete().where(
                AttachmentTextContent.attachment_id == attachment_id
            )
            db_session.execute(delete_stmt)
            db_session.commit()
            logger.info(f"Task {task_id}: Cleared any existing text content for attachment {attachment_id}")
        except Exception as del_err:
            logger.warning(f"Task {task_id}: Error clearing existing text content: {del_err}")
            db_session.rollback()

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
            # Retry if this could be a transient issue
            raise self.retry(
                exc=pdf_err, countdown=int(60 * (self.request.retries + 1))
            ) from pdf_err

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
            try:
                for page_num in range(total_pages):
                    try:
                        page = doc.load_page(page_num)
                        # Direct text extraction first
                        direct_text = (
                            page.get_text("text") or ""
                        )  # Default to empty string if None

                        page_text_to_save = direct_text  # Default to direct extraction

                        # OCR Fallback Logic
                        TEXT_LENGTH_THRESHOLD = 50  # Chars; Tune this threshold
                        if len(direct_text.strip()) < TEXT_LENGTH_THRESHOLD:
                            logger.info(
                                f"Task {task_id}: Page {page_num+1} has little direct text "
                                f"({len(direct_text.strip())} chars), attempting OCR."
                            )
                            try:
                                # Configure Tesseract path from settings
                                pytesseract.pytesseract.tesseract_cmd = (
                                    settings.effective_tesseract_path
                                )

                                # Render page to an image (e.g., PNG) at higher DPI for better OCR
                                zoom = 4  # zoom factor 4 => 300 DPI (approx)
                                mat = fitz.Matrix(zoom, zoom)
                                # alpha=False for non-transparent image
                                pix = page.get_pixmap(matrix=mat, alpha=False)

                                img_data = pix.tobytes("png")  # Use PNG format

                                if not img_data:
                                    logger.warning(
                                        f"Task {task_id}: Failed to get image bytes for page "
                                        f"{page_num+1}."
                                    )
                                else:
                                    img = Image.open(io.BytesIO(img_data))

                                    # Perform OCR using configured languages
                                    langs = "+".join(settings.TESSERACT_LANGUAGES)
                                    ocr_text = pytesseract.image_to_string(
                                        img, lang=langs
                                    )

                                    if (
                                        ocr_text.strip()
                                    ):  # Only use OCR text if it's not empty
                                        page_text_to_save = ocr_text
                                        logger.info(
                                            f"Task {task_id}: OCR successful for page {page_num+1}, "
                                            f"length: {len(ocr_text)}, languages: {langs}"
                                        )
                                    else:
                                        logger.warning(
                                            f"Task {task_id}: OCR produced no text for page "
                                            f"{page_num+1}, keeping direct text (length: "
                                            f"{len(direct_text)})"
                                        )

                            except ImportError:
                                logger.error(
                                    f"Task {task_id}: Pytesseract or Pillow not installed. "
                                    f"Cannot perform OCR fallback. Path: {settings.effective_tesseract_path}"
                                )
                                # Sticks with direct_text
                            except pytesseract.TesseractNotFoundError:
                                logger.error(
                                    f"Task {task_id}: Tesseract executable not found at "
                                    f"{settings.effective_tesseract_path}. "
                                    "Ensure it's installed and path is correct."
                                )
                                # Sticks with direct_text
                            except Exception as ocr_err:
                                logger.error(
                                    f"Task {task_id}: OCR failed for page {page_num+1}: {ocr_err}"
                                )
                                # Sticks with direct_text

                        # Determine the source of the text (direct or OCR)
                        source = "OCR" if page_text_to_save != direct_text else "DIRECT"

                        # Create and save an entry for this page
                        text_content_entry = AttachmentTextContent(
                            attachment_id=attachment_id,
                            page_number=page_num + 1,
                            text_content=page_text_to_save,
                            source=source,
                            words_count=len(page_text_to_save.split()),
                            characters_count=len(page_text_to_save),
                        )
                        db_session.add(text_content_entry)
                        processed_pages += 1
                        logger.debug(
                            f"Task {task_id}: Processed page {page_num+1} with "
                            f"{len(page_text_to_save)} chars"
                        )

                    except Exception as page_err:
                        logger.error(
                            f"Task {task_id}: Error processing page {page_num+1}: {page_err}"
                        )
                        errors_on_pages += 1
                        check_error_threshold()  # Checks if we've hit the error threshold
                
                # Commit at the end of processing all pages
                db_session.commit()
                logger.info(
                    f"Task {task_id}: Committed all {total_pages} pages for attachment {attachment_id}"
                )
            except Exception as e:
                # Handle any exceptions during processing
                logger.error(f"Task {task_id}: Error during single transaction processing: {e}")
                db_session.rollback()
                raise e
        else:
            # Process PDF with periodic commits
            for page_num in range(total_pages):
                try:
                    page = doc.load_page(page_num)
                    # Direct text extraction first
                    direct_text = (
                        page.get_text("text") or ""
                    )  # Default to empty string if None

                    page_text_to_save = direct_text  # Default to direct extraction

                    # OCR Fallback Logic
                    TEXT_LENGTH_THRESHOLD = 50  # Chars; Tune this threshold
                    if len(direct_text.strip()) < TEXT_LENGTH_THRESHOLD:
                        logger.info(
                            f"Task {task_id}: Page {page_num+1} has little direct text "
                            f"({len(direct_text.strip())} chars), attempting OCR."
                        )
                        try:
                            # Configure Tesseract path from settings
                            pytesseract.pytesseract.tesseract_cmd = (
                                settings.effective_tesseract_path
                            )

                            # Render page to an image (e.g., PNG) at higher DPI for better OCR
                            zoom = 4  # zoom factor 4 => 300 DPI (approx)
                            mat = fitz.Matrix(zoom, zoom)
                            # alpha=False for non-transparent image
                            pix = page.get_pixmap(matrix=mat, alpha=False)

                            img_data = pix.tobytes("png")  # Use PNG format

                            if not img_data:
                                logger.warning(
                                    f"Task {task_id}: Failed to get image bytes for page "
                                    f"{page_num+1}."
                                )
                            else:
                                img = Image.open(io.BytesIO(img_data))

                                # Perform OCR using configured languages
                                langs = "+".join(settings.TESSERACT_LANGUAGES)
                                ocr_text = pytesseract.image_to_string(img, lang=langs)

                                if (
                                    ocr_text.strip()
                                ):  # Only use OCR text if it's not empty
                                    page_text_to_save = ocr_text
                                    logger.info(
                                        f"Task {task_id}: OCR successful for page {page_num+1}, "
                                        f"length: {len(ocr_text)}, languages: {langs}"
                                    )
                                else:
                                    logger.warning(
                                        f"Task {task_id}: OCR produced no text for page "
                                        f"{page_num+1}, keeping direct text (length: "
                                        f"{len(direct_text)})"
                                    )

                        except ImportError:
                            logger.error(
                                f"Task {task_id}: Pytesseract or Pillow not installed. "
                                f"Cannot perform OCR fallback. Path: {settings.effective_tesseract_path}"
                            )
                            # Sticks with direct_text
                        except pytesseract.TesseractNotFoundError:
                            logger.error(
                                f"Task {task_id}: Tesseract executable not found at "
                                f"{settings.effective_tesseract_path}. "
                                "Ensure it's installed and path is correct."
                            )
                            # Sticks with direct_text
                        except Exception as ocr_err:
                            # Catch other potential errors (PIL issues, tesseract runtime errors)
                            logger.warning(
                                f"Task {task_id}: OCR failed for page {page_num+1} of "
                                f"attachment {attachment_id}: {ocr_err}",
                                exc_info=True,
                            )
                            # Sticks with direct_text (which is already in page_text_to_save)

                    # Create and Save AttachmentTextContent record with the best text we have
                    text_content_entry = AttachmentTextContent(
                        attachment_id=attachment_id,
                        page_number=page_num + 1,  # Page numbers are 1-based
                        text_content=(
                            page_text_to_save.strip() if page_text_to_save else None
                        ),
                    )
                    db_session.add(text_content_entry)
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
                        # Direct db method call for commit - database calls need async_to_sync
                        try:
                            db_session.commit()
                            logger.info(
                                f"Task {task_id}: Committed batch of {page_commit_counter} "
                                f"pages for attachment {attachment_id}"
                            )
                            page_commit_counter = 0
                        except Exception as commit_err:
                            logger.error(
                                f"Task {task_id}: Failed to commit batch: {commit_err}"
                            )
                            db_session.rollback()
                            page_commit_counter = 0
                            # Track as errors and continue
                            errors_on_pages += min(
                                settings.PDF_BATCH_COMMIT_SIZE,
                                total_pages - processed_pages,
                            )
                            check_error_threshold()  # May raise ValueError if too many errors

                except Exception as page_err:
                    errors_on_pages += 1
                    logger.error(
                        f"Task {task_id}: Error processing page {page_num + 1} "
                        f"for attachment {attachment_id}: {page_err}"
                    )
                    # Direct db method call for rollback - database calls need async_to_sync
                    db_session.rollback()
                    page_commit_counter = 0  # Reset counter after rollback
                    check_error_threshold()  # May raise ValueError if too many errors
                    # Continue to next page if within error threshold

            # Commit any remaining entries after the loop
            if page_commit_counter > 0:
                # Direct db method call for commit - database calls need async_to_sync
                try:
                    db_session.commit()
                    logger.info(
                        f"Task {task_id}: Committed final batch of {page_commit_counter} "
                        f"pages for attachment {attachment_id}"
                    )
                except Exception as commit_err:
                    logger.error(
                        f"Task {task_id}: Failed to commit final batch: {commit_err}"
                    )
                    db_session.rollback()
                    # Track as errors
                    errors_on_pages += page_commit_counter
                    check_error_threshold()  # May raise ValueError if too many errors

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

        # Rollback any pending database changes
        if db:
            try:
                db_session.rollback()
                logger.info(
                    f"Task {task_id}: Database transaction rolled back for failed task."
                )
            except Exception as rb_err:
                logger.error(
                    f"Task {task_id}: Failed to rollback transaction: {rb_err}"
                )

        # Retry logic
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
            try:
                # TrackedAsyncSession.close() is async, we need to use async_to_sync
                db_session.close()
                logger.debug(
                    f"Task {task_id}: Database session closed for attachment {attachment_id}"
                )
            except Exception as close_err:
                logger.error(f"Task {task_id}: Failed to close database session: {close_err}")
