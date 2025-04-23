# Step 10: Trigger Task from AttachmentService

## Goal
Modify `AttachmentService.process_attachments` to dispatch the `process_pdf_attachment` Celery task when a PDF attachment is successfully saved.

## TDD (RED)
Write a test in `app/tests/test_unit/test_services/test_attachment_service.py` to verify that the `AttachmentService` correctly dispatches the OCR task for PDF attachments.

```python
# app/tests/test_unit/test_services/test_attachment_service.py - add or update
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import base64

@pytest.mark.asyncio
async def test_process_attachments_dispatches_ocr_task():
    """Test that process_attachments dispatches the OCR task for PDF attachments."""
    # Import the service and models
    from app.services.attachment_service import AttachmentService
    from app.models.email_data import Attachment
    
    # Create mock DB session
    mock_db_session = AsyncMock()
    
    # Create mock StorageService
    mock_storage = AsyncMock()
    mock_storage.save_file = AsyncMock(return_value="test-storage-uri")
    
    # Create sample attachment data
    pdf_attachment_data = {
        "name": "test.pdf",
        "content": base64.b64encode(b"PDF content").decode("utf-8"),
        "type": "application/pdf",
        "size": 123
    }
    
    non_pdf_attachment_data = {
        "name": "test.jpg",
        "content": base64.b64encode(b"JPG content").decode("utf-8"),
        "type": "image/jpeg",
        "size": 456
    }
    
    # Create service instance
    service = AttachmentService(db=mock_db_session, storage=mock_storage)
    
    # Test dispatching OCR task
    with patch('app.services.attachment_service.process_pdf_attachment') as mock_process_pdf_attachment:
        # Configure mock DB to set IDs when add is called
        mock_attachment_pdf = MagicMock(spec=Attachment)
        mock_attachment_pdf.id = None  # Start with no ID
        mock_attachment_pdf.content_type = "application/pdf"
        mock_attachment_pdf.filename = "test.pdf"
        
        mock_attachment_jpg = MagicMock(spec=Attachment)
        mock_attachment_jpg.id = None  # Start with no ID
        mock_attachment_jpg.content_type = "image/jpeg"
        mock_attachment_jpg.filename = "test.jpg"
        
        # Mock the Attachment constructor to return our mock objects
        with patch('app.services.attachment_service.Attachment') as MockAttachment:
            MockAttachment.side_effect = [mock_attachment_pdf, mock_attachment_jpg]
            
            # Mock flush to set IDs
            async def mock_flush(objects=None):
                if objects is None or mock_attachment_pdf in objects:
                    mock_attachment_pdf.id = 1
                if objects is None or mock_attachment_jpg in objects:
                    mock_attachment_jpg.id = 2
            
            mock_db_session.flush = AsyncMock(side_effect=mock_flush)
            
            # Call the method with both PDF and non-PDF attachments
            attachments = await service.process_attachments(
                email_id=123,
                attachment_data=[pdf_attachment_data, non_pdf_attachment_data]
            )
            
            # Verify both attachments were processed
            assert len(attachments) == 2
            
            # Verify the OCR task was called only for the PDF
            mock_process_pdf_attachment.delay.assert_called_once_with(attachment_id=1)
            
            # Verify it was called after flush (ID assignment)
            assert mock_db_session.flush.call_count > 0
            
            # Verify the task was not called for the non-PDF attachment
            assert mock_process_pdf_attachment.delay.call_count == 1
```

## Implementation (GREEN)

### 1. Import Task in AttachmentService

Add the import for the OCR task to `app/services/attachment_service.py`:

```python
# Add this import to app/services/attachment_service.py
from app.worker.tasks import process_pdf_attachment
```

### 2. Modify process_attachments Method

Update the `process_attachments` method in `AttachmentService` to dispatch the OCR task for PDF attachments:

```python
# Modify the process_attachments method in app/services/attachment_service.py
async def process_attachments(
    self, email_id: int, attachment_data: list[dict]
) -> list[Attachment]:
    """
    Process and store email attachments.
    
    Args:
        email_id: The ID of the parent Email
        attachment_data: List of attachment data dictionaries
        
    Returns:
        List of created Attachment objects
    """
    result = []
    
    for data in attachment_data:
        try:
            # Decode base64 content
            content = base64.b64decode(data["content"])
            
            # Create attachment record
            attachment = Attachment(
                email_id=email_id,
                filename=data.get("name", ""),
                content_type=data.get("type", ""),
                size=data.get("size", len(content)),
            )
            
            # Save file to storage
            storage_uri = await self.storage.save_file(content)
            attachment.storage_uri = storage_uri
            
            # Add attachment to database
            self.db.add(attachment)
            
            # Flush the session to get the attachment ID assigned by the database
            # We need the ID to pass to the Celery task.
            try:
                # Flush only the specific attachment object for efficiency
                await self.db.flush([attachment])
                logger.debug(f"Flushed attachment {attachment.filename}, assigned ID: {attachment.id}")
            except Exception as flush_err:
                logger.error(f"Failed to flush attachment {attachment.filename} to get ID: {flush_err}")
                # If flush fails, we can't get the ID, so don't dispatch the task
                result.append(attachment)  # Still append to results, but skip OCR
                continue  # Continue to the next attachment in the loop
            
            # Check if attachment ID was populated (should be after successful flush)
            if attachment.id is None:
                logger.error(f"Attachment {attachment.filename} did not get an ID after flush, cannot dispatch OCR task.")
                result.append(attachment)
                continue
            
            # Check if it's a PDF and dispatch the OCR task
            is_pdf = attachment.content_type == 'application/pdf' or \
                    (attachment.filename and attachment.filename.lower().endswith('.pdf'))
            
            if is_pdf:
                try:
                    logger.info(f"Dispatching OCR task for PDF attachment ID: {attachment.id}, Filename: {attachment.filename}")
                    # Ensure attachment_id is passed correctly as a keyword argument
                    process_pdf_attachment.delay(attachment_id=attachment.id)
                except Exception as dispatch_err:
                    # Log error if task dispatch fails, but don't fail the request
                    logger.error(f"Failed to dispatch Celery OCR task for attachment {attachment.id}: {dispatch_err}")
            
            result.append(attachment)
        except Exception as e:
            logger.error(f"Failed to process attachment: {e}", exc_info=True)
            # Continue with next attachment
    
    return result
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
Run the test to verify that the `AttachmentService` correctly dispatches the OCR task:
```bash
pytest app/tests/test_unit/test_services/test_attachment_service.py::test_process_attachments_dispatches_ocr_task
```

The test should now pass.

## Self-Verification Checklist
- [ ] Is the OCR task imported in `AttachmentService`?
- [ ] Is `db.flush([attachment])` called to ensure the attachment gets an ID?
- [ ] Is error handling implemented for flush failures?
- [ ] Is there a check to verify the attachment has an ID after flush?
- [ ] Is there a check to verify the attachment is a PDF?
- [ ] Is `process_pdf_attachment.delay()` called with the correct argument?
- [ ] Is error handling implemented for task dispatch failures?
- [ ] Do the changes maintain the existing behavior for non-PDF attachments?
- [ ] Do all tests pass?
- [ ] Do all quality checks pass?

After completing this step, stop and request approval before proceeding to Step 11. 