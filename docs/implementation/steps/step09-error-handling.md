# Step 9: Implement Task: Final Error Handling & Retries

## Goal
Ensure the Celery task's overall error handling, database rollback, Celery retries, and session closing are correctly implemented around the complete PDF processing logic.

## TDD (RED)
Write a test in `app/tests/test_unit/test_worker.py` to verify the task's error handling, retry mechanism, and resource cleanup.

```python
# app/tests/test_unit/test_worker.py - add or update
import pytest
from unittest.mock import patch, MagicMock, AsyncMock, call
from celery.exceptions import Retry, MaxRetriesExceededError

def test_process_pdf_attachment_error_handling_and_retries():
    """Test that the task properly handles errors, retries, and cleans up resources."""
    # Import the task
    from app.worker.tasks import process_pdf_attachment
    
    # Setup mocks
    mock_db_session = MagicMock()
    mock_attachment = MagicMock()
    mock_attachment.id = 1
    mock_attachment.storage_uri = "test-storage-uri"
    
    # Test error before PDF opening (e.g., storage error)
    with patch('app.worker.tasks.get_session', return_value=mock_db_session), \
         patch('app.worker.tasks.StorageService') as MockStorageService, \
         patch('app.worker.tasks.async_to_sync') as mock_async_to_sync:
        
        # Configure mocks
        mock_db_session.get.return_value = mock_attachment
        mock_storage = MagicMock()
        mock_storage.get_file = AsyncMock(side_effect=Exception("Storage error"))
        MockStorageService.return_value = mock_storage
        mock_async_to_sync.side_effect = lambda func: raise_(Exception("Storage error"))
        
        # Mock the task's retry method
        mock_task = MagicMock()
        mock_task.retry = MagicMock(side_effect=Retry())
        
        # Expect a Retry exception
        with pytest.raises(Retry):
            process_pdf_attachment(mock_task, 1)
        
        # Verify retry was called
        mock_task.retry.assert_called_once()
        
        # Verify session was closed
        mock_db_session.close.assert_called_once()
    
    # Test error during PDF opening
    with patch('app.worker.tasks.get_session', return_value=mock_db_session), \
         patch('app.worker.tasks.StorageService') as MockStorageService, \
         patch('app.worker.tasks.async_to_sync') as mock_async_to_sync, \
         patch('app.worker.tasks.fitz.open', side_effect=Exception("PDF open error")):
        
        # Configure mocks
        mock_db_session.get.return_value = mock_attachment
        mock_storage = MagicMock()
        mock_storage.get_file = AsyncMock(return_value=b'pdfbytes')
        MockStorageService.return_value = mock_storage
        mock_async_to_sync.return_value = lambda func: b'pdfbytes'
        
        # Mock the task's retry method
        mock_task = MagicMock()
        mock_task.retry = MagicMock(side_effect=Retry())
        
        # Expect a Retry exception
        with pytest.raises(Retry):
            process_pdf_attachment(mock_task, 1)
        
        # Verify retry was called
        mock_task.retry.assert_called_once()
        
        # Verify session was closed
        mock_db_session.close.assert_called_once()
    
    # Test max retries exceeded
    with patch('app.worker.tasks.get_session', return_value=mock_db_session), \
         patch('app.worker.tasks.StorageService') as MockStorageService, \
         patch('app.worker.tasks.async_to_sync') as mock_async_to_sync, \
         patch('app.worker.tasks.fitz.open', side_effect=Exception("PDF open error")):
        
        # Configure mocks
        mock_db_session.get.return_value = mock_attachment
        mock_storage = MagicMock()
        mock_storage.get_file = AsyncMock(return_value=b'pdfbytes')
        MockStorageService.return_value = mock_storage
        mock_async_to_sync.return_value = lambda func: b'pdfbytes'
        
        # Mock the task's retry method to raise MaxRetriesExceededError
        mock_task = MagicMock()
        mock_task.retry = MagicMock(side_effect=MaxRetriesExceededError())
        
        # Should not raise, but return error message
        result = process_pdf_attachment(mock_task, 1)
        
        # Verify retry was called
        mock_task.retry.assert_called_once()
        
        # Verify failure message is returned
        assert "failed" in result.lower()
        assert "max retries" in result.lower()
        
        # Verify session was closed
        mock_db_session.close.assert_called_once()

# Helper function for the test
def raise_(ex):
    raise ex
```

## Implementation (GREEN)

### 1. Review Current Error Handling

Review the existing error handling structure in `process_pdf_attachment` task and ensure it covers all necessary scenarios:

```python
# Review and refine the existing try-except-finally block
@shared_task(bind=True, max_retries=3, default_retry_delay=60, name='app.worker.tasks.process_pdf_attachment')
def process_pdf_attachment(self, attachment_id: int) -> str:
    """
    Celery task to OCR a PDF attachment page by page.
    Args:
        self: The task instance (automatically passed with bind=True).
        attachment_id: The ID of the Attachment record to process.

    Returns:
        A status message string.
    """
    task_id = self.request.id
    logger.info(f"Task {task_id}: Starting OCR process for attachment ID: {attachment_id}")

    db = None  # Initialize db to None for finally block safety
    try:
        # 1. Get database session
        db = get_session()  # Get a SYNC session

        # 2. Fetch Attachment
        attachment = db.get(Attachment, attachment_id)
        if not attachment:
            logger.error(f"Task {task_id}: Attachment {attachment_id} not found.")
            return f"Task {task_id}: Attachment {attachment_id} not found."
            
        if not attachment.storage_uri:
            logger.error(f"Task {task_id}: Attachment {attachment_id} has no storage URI.")
            return f"Task {task_id}: Attachment {attachment_id} has no storage URI."

        # 3. Retrieve PDF content from storage
        storage = StorageService()
        try:
            pdf_data = async_to_sync(storage.get_file)(attachment.storage_uri)
        except Exception as storage_err:
            logger.error(f"Task {task_id}: Failed to get PDF from storage {attachment.storage_uri}: {storage_err}")
            raise  # Re-raise to trigger retry

        if not pdf_data:
            logger.error(f"Task {task_id}: Could not retrieve PDF data from {attachment.storage_uri}")
            raise self.retry(exc=Exception(f"PDF data not found at {attachment.storage_uri}"), countdown=60)

        # 4. Open the PDF
        try:
            doc = fitz.open(stream=pdf_data, filetype="pdf")
            logger.info(f"Task {task_id}: Opened PDF for attachment {attachment_id}. Page count: {doc.page_count}")
        except Exception as pdf_err:
            logger.error(f"Task {task_id}: Failed to open PDF for attachment {attachment_id}: {pdf_err}")
            raise  # Re-raise to trigger retry

        # 5. Process pages
        # (existing page processing logic with OCR fallback)
        # ...

        # 6. Return success message
        status_msg = (
            f"Task {task_id}: Attachment {attachment_id} processed. "
            f"Pages: {doc.page_count}, Success: {processed_pages}, Errors: {errors_on_pages}."
        )
        logger.info(status_msg)
        return status_msg

    except Retry:
        # Important: Re-raise Retry exceptions to let Celery handle them
        raise
    except Exception as e:
        logger.error(f"Task {task_id}: Error processing attachment {attachment_id}: {e}", exc_info=True)
        
        # Rollback any pending database changes
        if db:
            try:
                db.rollback()
                logger.info(f"Task {task_id}: Database transaction rolled back for failed task.")
            except Exception as rb_err:
                logger.error(f"Task {task_id}: Failed to rollback transaction: {rb_err}")
        
        # Retry logic
        try:
            # Retry the task with exponential backoff
            logger.warning(f"Task {task_id}: Retrying task for attachment {attachment_id} due to error: {e}")
            # Ensure exc is passed for Celery >= 5
            raise self.retry(exc=e, countdown=int(60 * (self.request.retries + 1)))
        except MaxRetriesExceededError:
            logger.error(f"Task {task_id}: Max retries exceeded for attachment {attachment_id}. Giving up.")
            return f"Task {task_id}: Failed attachment {attachment_id} after max retries."
        except Retry:
            # Re-raise if self.retry itself raises Retry
            raise
        except Exception as retry_err:
            logger.error(f"Task {task_id}: Failed to enqueue retry for task {attachment_id}: {retry_err}")
            return f"Task {task_id}: Failed attachment {attachment_id}, could not retry."
    finally:
        # Ensure database session is always closed
        if db:
            try:
                db.close()
                logger.debug(f"Task {task_id}: Database session closed for attachment {attachment_id}")
            except Exception as close_err:
                logger.error(f"Task {task_id}: Error closing database session: {close_err}")
```

### 2. Implement Any Missing Error Handling

Add any missing error handling for specific scenarios:

```python
# Add additional error handling for specific scenarios as needed
# For example, to handle errors related to database commits in the batch mode:

# Inside the non-single transaction loop, add error handling for commits:
try:
    db.commit()
    logger.info(f"Task {task_id}: Committed batch of {page_commit_counter} pages for attachment {attachment_id}")
    page_commit_counter = 0
except Exception as commit_err:
    logger.error(f"Task {task_id}: Failed to commit batch: {commit_err}")
    db.rollback()
    page_commit_counter = 0
    # Consider if this should be retried or just continue
    # For now, let's continue and track it as an error
    errors_on_pages += min(settings.PDF_BATCH_COMMIT_SIZE, total_pages - processed_pages)
    check_error_threshold()  # May raise ValueError if too many errors
```

## Quality Check (REFACTOR)
Run the following code quality tools and fix any issues:
```bash
black .
isort .
flake8 .
mypy app
```

## Testing (REFACTOR)
Run the test to verify the error handling and retry logic:
```bash
pytest app/tests/test_unit/test_worker.py::test_process_pdf_attachment_error_handling_and_retries
```

The test should now pass.

## Self-Verification Checklist
- [ ] Is the main try-except-finally structure properly implemented?
- [ ] Is `db.rollback()` called when exceptions occur?
- [ ] Is `self.retry()` called with the original exception?
- [ ] Is `MaxRetriesExceededError` properly handled?
- [ ] Is the database session always closed in the `finally` block?
- [ ] Are specific error scenarios (database errors, PDF errors, storage errors) properly handled?
- [ ] Are appropriate error messages logged for each failure scenario?
- [ ] Is the task status message clear about success or failure?
- [ ] Do all tests pass?
- [ ] Do all quality checks pass?

After completing this step, stop and request approval before proceeding to Step 10. 