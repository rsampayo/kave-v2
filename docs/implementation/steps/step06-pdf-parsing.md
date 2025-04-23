# Step 6: Implement Task: Basic PyMuPDF Parsing (Page Count)

## Goal
Add PyMuPDF logic to open the retrieved PDF data and log the page count.

## TDD (RED)
Write a test in `app/tests/test_unit/test_worker.py` to verify that the task correctly opens a PDF and logs its page count.

```python
# app/tests/test_unit/test_worker.py - add or update
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

def test_process_pdf_attachment_open_pdf():
    """Test that the task opens the PDF and gets the page count."""
    # Import the task
    from app.worker.tasks import process_pdf_attachment
    
    # Setup mocks
    mock_db_session = MagicMock()
    mock_attachment = MagicMock()
    mock_attachment.id = 1
    mock_attachment.storage_uri = "test-storage-uri"
    
    mock_storage = MagicMock()
    mock_storage_get_file = AsyncMock(return_value=b'pdfbytes')
    mock_storage.get_file = mock_storage_get_file
    
    # Create a mock document with page count
    mock_doc = MagicMock()
    mock_doc.page_count = 3
    
    # Mock fitz.open to return our mock document
    with patch('app.worker.tasks.get_session', return_value=mock_db_session), \
         patch('app.worker.tasks.StorageService', return_value=mock_storage), \
         patch('app.worker.tasks.async_to_sync') as mock_async_to_sync, \
         patch('app.worker.tasks.fitz.open', return_value=mock_doc) as mock_fitz_open:
        
        # Configure mocks
        mock_db_session.get.return_value = mock_attachment
        mock_async_to_sync.return_value = lambda func: b'pdfbytes'
        
        # Call the task
        result = process_pdf_attachment(MagicMock(), 1)
        
        # Verify fitz.open was called with the correct arguments
        mock_fitz_open.assert_called_once_with(stream=b'pdfbytes', filetype="pdf")
        
        # Verify the page count is logged (indirectly through success message)
        assert "pages: 3" in result.lower()
    
    # Test error when opening PDF
    with patch('app.worker.tasks.get_session', return_value=mock_db_session), \
         patch('app.worker.tasks.StorageService', return_value=mock_storage), \
         patch('app.worker.tasks.async_to_sync') as mock_async_to_sync, \
         patch('app.worker.tasks.fitz.open', side_effect=Exception("PDF open error")) as mock_fitz_open:
        
        # Configure mocks
        mock_db_session.get.return_value = mock_attachment
        mock_async_to_sync.return_value = lambda func: b'pdfbytes'
        
        # Call the task
        result = process_pdf_attachment(MagicMock(), 1)
        
        # Verify error handling
        assert "failed to open pdf" in result.lower()
```

## Implementation (GREEN)

### 1. Add PyMuPDF import

Add the PyMuPDF import to `app/worker/tasks.py`:

```python
# Add this import to app/worker/tasks.py
import fitz
```

### 2. Implement PDF opening logic

Modify the `process_pdf_attachment` task in `app/worker/tasks.py` to open the PDF and get the page count:

```python
# Inside the try block of process_pdf_attachment, after getting pdf_data
# Replace the "--- PDF processing logic (Next Steps) ---" comment and placeholder return

# Open the PDF with PyMuPDF
try:
    doc = fitz.open(stream=pdf_data, filetype="pdf")
    logger.info(f"Task {task_id}: Opened PDF for attachment {attachment_id}. Page count: {doc.page_count}")
except Exception as pdf_err:
    logger.error(f"Task {task_id}: Failed to open PDF for attachment {attachment_id}: {pdf_err}")
    # Decide if this is retryable. Corrupt PDF likely isn't.
    # For now, we'll just return failure status. Could retry if it might be transient.
    return f"Task {task_id}: Failed to open PDF for attachment {attachment_id}"

# --- Page processing logic will go here ---
# Placeholder success for this step
return f"Task {task_id}: Successfully opened PDF for {attachment_id}, pages: {doc.page_count}"
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
Run the test to verify the PDF opening logic:
```bash
pytest app/tests/test_unit/test_worker.py::test_process_pdf_attachment_open_pdf
```

The test should now pass.

## Self-Verification Checklist
- [ ] Is `fitz` (PyMuPDF) imported correctly?
- [ ] Is `fitz.open` called with the correct arguments (stream and filetype)?
- [ ] Is the PDF page count logged?
- [ ] Is error handling implemented for PDF opening failures?
- [ ] Does the task return appropriate success/failure messages?
- [ ] Do all tests pass?
- [ ] Do all quality checks pass?

After completing this step, stop and request approval before proceeding to Step 7. 