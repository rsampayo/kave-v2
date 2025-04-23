# Step 7: Implement Task: Loop & Direct Text Extraction & DB Save

## Goal
Loop through the PDF pages, extract text directly using `page.get_text()`, and save each page's text to the `AttachmentTextContent` table.

## TDD (RED)
Write a test in `app/tests/test_unit/test_worker.py` to verify that the task correctly loops through pages, extracts text, and saves it to the database.

```python
# app/tests/test_unit/test_worker.py - add or update
import pytest
from unittest.mock import patch, MagicMock, AsyncMock, call

def test_process_pdf_attachment_text_extraction_and_save():
    """Test that the task extracts text from PDF pages and saves to the database."""
    # Import the task and model
    from app.worker.tasks import process_pdf_attachment
    from app.models.attachment_text_content import AttachmentTextContent
    
    # Setup mocks
    mock_db_session = MagicMock()
    mock_attachment = MagicMock()
    mock_attachment.id = 1
    mock_attachment.storage_uri = "test-storage-uri"
    
    mock_storage = MagicMock()
    mock_storage_get_file = AsyncMock(return_value=b'pdfbytes')
    mock_storage.get_file = mock_storage_get_file
    
    # Create mock document and pages
    mock_doc = MagicMock()
    mock_doc.page_count = 3
    
    # Create mock pages
    mock_pages = []
    for i in range(3):
        mock_page = MagicMock()
        mock_page.get_text.return_value = f"Text from page {i+1}"
        mock_pages.append(mock_page)
    
    # Make doc.load_page return the appropriate mock page
    mock_doc.load_page = lambda page_num: mock_pages[page_num]
    
    # Test single transaction mode
    with patch('app.worker.tasks.get_session', return_value=mock_db_session), \
         patch('app.worker.tasks.StorageService', return_value=mock_storage), \
         patch('app.worker.tasks.async_to_sync') as mock_async_to_sync, \
         patch('app.worker.tasks.fitz.open', return_value=mock_doc), \
         patch('app.worker.tasks.settings.PDF_USE_SINGLE_TRANSACTION', True), \
         patch('app.worker.tasks.AttachmentTextContent') as MockAttachmentTextContent:
        
        # Configure mocks
        mock_db_session.get.return_value = mock_attachment
        mock_async_to_sync.return_value = lambda func: b'pdfbytes'
        mock_db_session.begin = MagicMock(return_value=MagicMock(__enter__=MagicMock(), __exit__=MagicMock()))
        
        # Call the task
        result = process_pdf_attachment(MagicMock(), 1)
        
        # Verify that text was extracted and saved for each page
        assert MockAttachmentTextContent.call_count == 3
        # Verify add was called for each page
        assert mock_db_session.add.call_count == 3
        # Verify begin() was called (single transaction)
        assert mock_db_session.begin.call_count == 1
        
        # Verify success status including page counts
        assert "pages: 3" in result.lower()
        assert "success: 3" in result.lower()
    
    # Test batch transaction mode
    with patch('app.worker.tasks.get_session', return_value=mock_db_session), \
         patch('app.worker.tasks.StorageService', return_value=mock_storage), \
         patch('app.worker.tasks.async_to_sync') as mock_async_to_sync, \
         patch('app.worker.tasks.fitz.open', return_value=mock_doc), \
         patch('app.worker.tasks.settings.PDF_USE_SINGLE_TRANSACTION', False), \
         patch('app.worker.tasks.settings.PDF_BATCH_COMMIT_SIZE', 2), \
         patch('app.worker.tasks.AttachmentTextContent') as MockAttachmentTextContent:
        
        # Reset mock counts
        mock_db_session.reset_mock()
        MockAttachmentTextContent.reset_mock()
        
        # Configure mocks
        mock_db_session.get.return_value = mock_attachment
        mock_async_to_sync.return_value = lambda func: b'pdfbytes'
        
        # Call the task
        result = process_pdf_attachment(MagicMock(), 1)
        
        # Verify that text was extracted and saved for each page
        assert MockAttachmentTextContent.call_count == 3
        # Verify add was called for each page
        assert mock_db_session.add.call_count == 3
        # Verify commit was called at least once (should be twice: after page 2 and after page 3)
        assert mock_db_session.commit.call_count >= 1
        
        # Verify success status
        assert "pages: 3" in result.lower()
        assert "success: 3" in result.lower()
    
    # Test error handling during page processing
    with patch('app.worker.tasks.get_session', return_value=mock_db_session), \
         patch('app.worker.tasks.StorageService', return_value=mock_storage), \
         patch('app.worker.tasks.async_to_sync') as mock_async_to_sync, \
         patch('app.worker.tasks.fitz.open', return_value=mock_doc), \
         patch('app.worker.tasks.settings.PDF_USE_SINGLE_TRANSACTION', False), \
         patch('app.worker.tasks.settings.PDF_BATCH_COMMIT_SIZE', 2), \
         patch('app.worker.tasks.settings.PDF_MAX_ERROR_PERCENTAGE', 50.0), \
         patch('app.worker.tasks.AttachmentTextContent') as MockAttachmentTextContent:
        
        # Reset mock counts
        mock_db_session.reset_mock()
        MockAttachmentTextContent.reset_mock()
        
        # Configure mocks
        mock_db_session.get.return_value = mock_attachment
        mock_async_to_sync.return_value = lambda func: b'pdfbytes'
        
        # Make the second page raise an exception
        mock_pages[1].get_text.side_effect = Exception("Text extraction error")
        
        # Call the task
        result = process_pdf_attachment(MagicMock(), 1)
        
        # Verify rollback was called
        assert mock_db_session.rollback.call_count >= 1
        
        # Verify partial success status
        assert "pages: 3" in result.lower()
        assert "success: 2" in result.lower()  # 2 out of 3 pages succeeded
        assert "errors: 1" in result.lower()  # 1 page had an error
```

## Implementation (GREEN)

### 1. Add Model Import

Add the `AttachmentTextContent` model import to `app/worker/tasks.py`:

```python
# Add this import to app/worker/tasks.py
from app.models.attachment_text_content import AttachmentTextContent
```

### 2. Implement Text Extraction and DB Save Logic

Modify the `process_pdf_attachment` task in `app/worker/tasks.py` to extract and save text from each page:

```python
# Inside the try block after the doc is created and page count logged
# Replace the "--- Page processing logic will go here ---" comment

# Initialize counters
page_commit_counter = 0
processed_pages = 0
errors_on_pages = 0
total_pages = doc.page_count

def check_error_threshold():
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
                page_text = page.get_text("text") or ""  # Default to empty string if None

                # Create and Save AttachmentTextContent record
                text_content_entry = AttachmentTextContent(
                    attachment_id=attachment_id,
                    page_number=page_num + 1,  # Page numbers are 1-based
                    text_content=page_text.strip() if page_text else None
                )
                db.add(text_content_entry)
                processed_pages += 1
                logger.debug(f"Task {task_id}: Added page {page_num + 1}/{total_pages} content for attachment {attachment_id}")

            except Exception as page_err:
                errors_on_pages += 1
                logger.error(f"Task {task_id}: Error processing page {page_num + 1} for attachment {attachment_id}: {page_err}")
                check_error_threshold()  # May raise ValueError if too many errors
                # Continue to next page if within error threshold

else:
    # Process PDF with periodic commits
    for page_num in range(total_pages):
        try:
            page = doc.load_page(page_num)
            # Direct text extraction
            page_text = page.get_text("text") or ""  # Default to empty string if None

            # Create and Save AttachmentTextContent record
            text_content_entry = AttachmentTextContent(
                attachment_id=attachment_id,
                page_number=page_num + 1,  # Page numbers are 1-based
                text_content=page_text.strip() if page_text else None
            )
            db.add(text_content_entry)
            page_commit_counter += 1
            processed_pages += 1
            logger.debug(f"Task {task_id}: Added page {page_num + 1}/{total_pages} content for attachment {attachment_id}")

            # Commit periodically if batch size is set
            if settings.PDF_BATCH_COMMIT_SIZE > 0 and page_commit_counter >= settings.PDF_BATCH_COMMIT_SIZE:
                db.commit()
                logger.info(f"Task {task_id}: Committed batch of {page_commit_counter} pages for attachment {attachment_id}")
                page_commit_counter = 0

        except Exception as page_err:
            errors_on_pages += 1
            logger.error(f"Task {task_id}: Error processing page {page_num + 1} for attachment {attachment_id}: {page_err}")
            db.rollback()  # Rollback current batch on page error
            page_commit_counter = 0  # Reset counter after rollback
            check_error_threshold()  # May raise ValueError if too many errors
            # Continue to next page if within error threshold

    # Commit any remaining entries after the loop
    if page_commit_counter > 0:
        db.commit()
        logger.info(f"Task {task_id}: Committed final batch of {page_commit_counter} pages for attachment {attachment_id}")

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
Run the test to verify the text extraction and database saving logic:
```bash
pytest app/tests/test_unit/test_worker.py::test_process_pdf_attachment_text_extraction_and_save
```

The test should now pass.

## Self-Verification Checklist
- [ ] Is the `AttachmentTextContent` model imported?
- [ ] Are both transaction modes implemented (single transaction and batched commits)?
- [ ] Is the page loop implemented correctly for each transaction mode?
- [ ] Is `page.get_text()` called to extract text from each page?
- [ ] Are `AttachmentTextContent` objects created with the correct data?
- [ ] Is `db.add()` called for each page?
- [ ] Is `db.commit()` called according to the batch size setting?
- [ ] Is `db.rollback()` called on page errors?
- [ ] Is the error threshold check implemented?
- [ ] Are appropriate counters maintained (processed pages, errors)?
- [ ] Is a detailed status message returned?
- [ ] Do all tests pass?
- [ ] Do all quality checks pass?

After completing this step, stop and request approval before proceeding to Step 8. 