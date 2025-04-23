# Step 5: Implement Task: Fetch Attachment & PDF Data

## Goal
Add logic to the Celery task to fetch the `Attachment` record and retrieve its PDF data from storage using `StorageService`. Handle errors if the attachment or its data isn't found.

## TDD (RED)
Write a test in `app/tests/test_unit/test_worker.py` to verify that the task fetches attachment data correctly and handles various error scenarios.

```python
# app/tests/test_unit/test_worker.py - add or update
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from sqlalchemy.orm import Session

def test_process_pdf_attachment_data_fetching():
    """Test the data fetching part of the PDF processing task."""
    # Import the task
    from app.worker.tasks import process_pdf_attachment
    
    # 1. Setup mocks
    mock_db_session = MagicMock(spec=Session)
    mock_attachment = MagicMock()
    mock_attachment.id = 1
    mock_attachment.storage_uri = "test-storage-uri"
    
    mock_storage = MagicMock()
    mock_storage_get_file = AsyncMock(return_value=b'pdfbytes')
    mock_storage.get_file = mock_storage_get_file
    
    # 2. Test successful data fetching
    with patch('app.worker.tasks.get_session', return_value=mock_db_session), \
         patch('app.worker.tasks.StorageService', return_value=mock_storage), \
         patch('app.worker.tasks.async_to_sync') as mock_async_to_sync, \
         patch('app.worker.tasks.Attachment') as MockAttachment:
        
        # Configure mocks
        mock_db_session.get.return_value = mock_attachment
        MockAttachment.__name__ = 'Attachment'  # For logging
        # Setup async_to_sync to return the async function's result
        mock_async_to_sync.return_value = lambda func: mock_storage_get_file.return_value
        
        # Call the task function directly
        result = process_pdf_attachment(MagicMock(), 1)
        
        # Verify the attachment was fetched
        mock_db_session.get.assert_called_once()
        # Verify storage.get_file was called
        mock_storage_get_file.assert_called_once_with("test-storage-uri")
        # Verify the task returned a success message
        assert "Successfully fetched data" in result
    
    # 3. Test attachment not found
    with patch('app.worker.tasks.get_session', return_value=mock_db_session), \
         patch('app.worker.tasks.StorageService', return_value=mock_storage), \
         patch('app.worker.tasks.Attachment') as MockAttachment:
        
        # Configure mocks
        mock_db_session.get.return_value = None
        
        # Call the task function directly
        result = process_pdf_attachment(MagicMock(), 1)
        
        # Verify the task returned an error message
        assert "not found" in result.lower()
    
    # 4. Test attachment has no storage_uri
    with patch('app.worker.tasks.get_session', return_value=mock_db_session), \
         patch('app.worker.tasks.StorageService', return_value=mock_storage), \
         patch('app.worker.tasks.Attachment') as MockAttachment:
        
        # Configure mocks
        mock_attachment_no_uri = MagicMock()
        mock_attachment_no_uri.id = 1
        mock_attachment_no_uri.storage_uri = None
        mock_db_session.get.return_value = mock_attachment_no_uri
        
        # Call the task function directly
        result = process_pdf_attachment(MagicMock(), 1)
        
        # Verify the task returned an error message
        assert "no storage uri" in result.lower()
    
    # 5. Test storage.get_file returns None
    with patch('app.worker.tasks.get_session', return_value=mock_db_session), \
         patch('app.worker.tasks.StorageService', return_value=mock_storage), \
         patch('app.worker.tasks.async_to_sync') as mock_async_to_sync, \
         patch('app.worker.tasks.Attachment') as MockAttachment:
        
        # Configure mocks
        mock_db_session.get.return_value = mock_attachment
        mock_storage_get_file.return_value = None
        # Setup async_to_sync to return the async function's result
        mock_async_to_sync.return_value = lambda func: None
        
        # Expect task to raise Retry exception if the data isn't found
        with pytest.raises(Exception):
            process_pdf_attachment(MagicMock(), 1)
```

## Implementation (GREEN)

### 1. Add required imports

Add the necessary imports to `app/worker/tasks.py`:

```python
# Add these imports to app/worker/tasks.py
from app.db.session import get_session
from app.services.storage_service import StorageService
from app.models.email_data import Attachment
from asgiref.sync import async_to_sync
```

### 2. Implement the data fetching logic

Modify the `process_pdf_attachment` task in `app/worker/tasks.py` to fetch the attachment and its data:

```python
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
    task_id = self.request.id # Get task ID for logging
    logger.info(f"Task {task_id}: Starting OCR process for attachment ID: {attachment_id}")

    db = None # Initialize db to None for finally block safety
    try:
        # Assuming a synchronous session helper for standard Celery workers
        # Adapt if using async workers or event loops within tasks.
        db = get_session() # Get a SYNC session

        # 1. Fetch Attachment metadata (using sync session methods)
        attachment = db.get(Attachment, attachment_id) # Use sync session's get
        if not attachment:
            logger.error(f"Task {task_id}: Attachment {attachment_id} not found.")
            return f"Task {task_id}: Attachment {attachment_id} not found."
        if not attachment.storage_uri:
             logger.error(f"Task {task_id}: Attachment {attachment_id} has no storage URI.")
             return f"Task {task_id}: Attachment {attachment_id} has no storage URI."

        logger.info(f"Task {task_id}: Found attachment {attachment_id} with URI: {attachment.storage_uri}")

        # 2. Retrieve PDF content from storage (bridging sync task to async storage)
        storage = StorageService()
        try:
            # Use async_to_sync to bridge sync (task) to async (storage)
            pdf_data = async_to_sync(storage.get_file)(attachment.storage_uri)
        except Exception as storage_err:
             logger.error(f"Task {task_id}: Failed to get PDF from storage {attachment.storage_uri}: {storage_err}")
             raise # Re-raise to potentially trigger retry

        if not pdf_data:
            logger.error(f"Task {task_id}: Could not retrieve PDF data from {attachment.storage_uri}")
            # Consider retrying if this might be transient
            raise self.retry(exc=Exception(f"PDF data not found at {attachment.storage_uri}"), countdown=60)

        logger.info(f"Task {task_id}: Successfully retrieved PDF data ({len(pdf_data)} bytes) for attachment {attachment_id}")

        # --- PDF processing logic (Next Steps) ---
        # Placeholder success return for this step
        return f"Task {task_id}: Successfully fetched data for attachment {attachment_id}"

    except Retry:
        # Important: Re-raise Retry exceptions to let Celery handle them
        raise
    except Exception as e:
        logger.error(f"Task {task_id}: Error processing attachment {attachment_id}: {e}", exc_info=True)
        # Rollback not needed yet
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
        if db:
            db.close() # Ensure session is always closed
            logger.debug(f"Task {task_id}: Database session closed for attachment {attachment_id}")
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
Run the test to verify the data fetching logic:
```bash
pytest app/tests/test_unit/test_worker.py::test_process_pdf_attachment_data_fetching
```

The test should now pass.

## Self-Verification Checklist
- [ ] Is `get_session` imported and used to get a database session?
- [ ] Is `StorageService` imported and instantiated?
- [ ] Is `Attachment` imported and used to fetch the attachment record?
- [ ] Is `async_to_sync` imported and used to call the async `storage.get_file` method?
- [ ] Does the code check if the attachment exists?
- [ ] Does the code check if the attachment has a storage_uri?
- [ ] Does the code check if pdf_data is returned from storage?
- [ ] Is proper error handling implemented for missing attachments?
- [ ] Is proper error handling implemented for storage errors?
- [ ] Is the session closed in the finally block?
- [ ] Do all tests pass?
- [ ] Do all quality checks pass?

After completing this step, stop and request approval before proceeding to Step 6. 