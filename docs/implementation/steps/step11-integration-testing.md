# Step 11: Integration Testing

## Goal
Verify the end-to-end flow from webhook reception to OCR text being saved in the database.

## TDD (RED)
Create an integration test to verify that when a webhook containing a PDF attachment is processed, the OCR text is correctly extracted and stored in the database.

```python
# app/tests/test_integration/test_api/test_pdf_ocr_flow.py
import base64
import json
import os
import time
from pathlib import Path
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.email_data import Email, Attachment
from app.models.attachment_text_content import AttachmentTextContent

# Path to a small sample PDF for testing
SAMPLE_PDF_PATH = Path(__file__).parent.parent / "test_data" / "sample.pdf"

def create_test_webhook_payload(pdf_path):
    """Create a test webhook payload with a PDF attachment."""
    # Read the PDF file
    with open(pdf_path, "rb") as f:
        pdf_content = f.read()
    
    # Create a webhook payload with the PDF attachment
    payload = {
        "event": "inbound",
        "ts": int(time.time()),
        "msg": {
            "subject": "Test Email with PDF Attachment",
            "from_email": "test@example.com",
            "to": [{"email": "recipient@example.com", "name": "Recipient"}],
            "attachments": [
                {
                    "name": "test-document.pdf",
                    "type": "application/pdf",
                    "content": base64.b64encode(pdf_content).decode("utf-8"),
                    "size": len(pdf_content)
                }
            ],
            "html": "<p>This is a test email with a PDF attachment.</p>",
            "text": "This is a test email with a PDF attachment."
        }
    }
    
    return payload

@pytest.mark.asyncio
async def test_pdf_ocr_flow(async_client: AsyncClient, db_session):
    """Test the complete flow from webhook to OCR text storage."""
    # Check if sample PDF exists, if not create a minimal one
    if not os.path.exists(SAMPLE_PDF_PATH):
        pytest.skip(f"Sample PDF not found at {SAMPLE_PDF_PATH}, please create one for this test")
    
    # Configure Celery for eager execution (synchronous) during tests
    # This is typically done in pytest.ini or test setup
    
    # Create webhook payload with PDF attachment
    payload = create_test_webhook_payload(SAMPLE_PDF_PATH)
    
    # Patch storage and OCR functions to avoid external dependencies
    with pytest.MonkeyPatch.context() as mp:
        # Mock storage to return a predictable URI and actually store content in memory
        storage_data = {}
        
        async def mock_save_file(self, content):
            uri = f"test:///attachments/{hash(content)}"
            storage_data[uri] = content
            return uri
        
        async def mock_get_file(self, uri):
            return storage_data.get(uri)
        
        # Apply the mocks
        from app.services.storage_service import StorageService
        mp.setattr(StorageService, "save_file", mock_save_file)
        mp.setattr(StorageService, "get_file", mock_get_file)
        
        # Optional: Mock pytesseract if needed
        # import pytesseract
        # mp.setattr(pytesseract, "image_to_string", lambda *args, **kwargs: "OCR text from test")
        
        # Send the webhook
        response = await async_client.post(
            "/v1/webhooks/mandrill",
            content=json.dumps(payload),
            headers={"Content-Type": "application/json"}
        )
        
        # Verify webhook was accepted
        assert response.status_code == 202
        
        # Allow some time for the task to complete (since it's running eagerly)
        await asyncio.sleep(1)
        
        # Query the database to verify data was saved correctly
        
        # 1. Check Email exists
        email_query = select(Email).where(Email.subject == payload["msg"]["subject"])
        email_result = await db_session.execute(email_query)
        email = email_result.scalar_one_or_none()
        assert email is not None, "Email not found in database"
        
        # 2. Check Attachment exists
        attachment_query = select(Attachment).where(Attachment.email_id == email.id)
        attachment_result = await db_session.execute(attachment_query)
        attachment = attachment_result.scalar_one_or_none()
        assert attachment is not None, "Attachment not found in database"
        assert attachment.content_type == "application/pdf"
        assert attachment.storage_uri is not None
        
        # 3. Check AttachmentTextContent entries exist
        content_query = select(AttachmentTextContent).where(
            AttachmentTextContent.attachment_id == attachment.id
        )
        content_result = await db_session.execute(content_query)
        content_entries = content_result.scalars().all()
        
        # Verify we have at least one content entry
        assert len(content_entries) > 0, "No OCR text content entries found"
        
        # Verify the text content is not empty for at least one page
        has_text = any(entry.text_content and len(entry.text_content) > 0 for entry in content_entries)
        assert has_text, "No text content was extracted by OCR"
        
        # Optional: Verify specific content if you're using a known PDF
        # first_page = next(entry for entry in content_entries if entry.page_number == 1)
        # assert "Expected text" in first_page.text_content
```

## Setup Test Data

Create a small sample PDF for testing:

1. Create the test data directory if it doesn't exist:
```bash
mkdir -p app/tests/test_integration/test_data
```

2. Create or obtain a small sample PDF file for testing. You can:
   - Create a simple PDF using a tool like LibreOffice, Microsoft Word, or an online PDF generator.
   - Use a pre-existing sample PDF if you have one.
   - Place the PDF in `app/tests/test_integration/test_data/sample.pdf`.

## Configure Celery for Testing

Update the test configuration to enable Celery eager mode during tests:

1. Add to `pytest.ini` or `pyproject.toml [tool.pytest.ini_options]`:
```ini
[tool.pytest.ini_options]
env = [
    "CELERY_TASK_ALWAYS_EAGER=True",
    "CELERY_TASK_EAGER_PROPAGATES=True"
]
```

2. Alternatively, create a fixture in `conftest.py`:
```python
# app/tests/conftest.py - add this
import pytest
from celery.contrib.testing.app import TestApp

@pytest.fixture(autouse=True)
def celery_eager():
    """Configure Celery to execute tasks eagerly (synchronously) during tests."""
    from app.worker.celery_app import celery_app
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True
    return celery_app
```

## Implementation (GREEN)

For this step, the implementation primarily consists of writing and running the integration test. The code we've already implemented in previous steps should handle the actual functionality.

### 1. Create the Test Data Directory

```bash
mkdir -p app/tests/test_integration/test_data
```

### 2. Add a Sample PDF

Create or obtain a small sample PDF and save it to `app/tests/test_integration/test_data/sample.pdf`.

### 3. Update Test Configuration

Add the Celery configuration to your pytest configuration as described above.

### 4. Run the Integration Test

```bash
pytest app/tests/test_integration/test_api/test_pdf_ocr_flow.py -v
```

## Troubleshooting

If the integration test fails, check the following:

1. **Sample PDF Access:** Ensure the test can find and read the sample PDF file.
2. **Celery Configuration:** Verify that Celery is running in eager mode during tests.
3. **Storage Mocking:** Check that the storage service mocking is correctly storing and retrieving PDF data.
4. **Task Execution:** Add debug logging to see if the OCR task is being triggered and executed.
5. **Database Queries:** Verify that the database queries are finding the correct records.

## Quality Check (REFACTOR)
Run the following code quality tools and fix any issues:
```bash
black .
isort .
flake8 .
mypy app
```

## Testing (REFACTOR)
Run the integration test:
```bash
pytest app/tests/test_integration/test_api/test_pdf_ocr_flow.py -v
```

The test should now pass, demonstrating that the entire flow works as expected.

## Self-Verification Checklist
- [ ] Is the test data directory created?
- [ ] Is a sample PDF file available for testing?
- [ ] Is Celery configured for eager execution during tests?
- [ ] Does the test create a valid webhook payload with a PDF attachment?
- [ ] Does the test correctly mock the storage service?
- [ ] Does the test verify that the Email record was created?
- [ ] Does the test verify that the Attachment record was created?
- [ ] Does the test verify that AttachmentTextContent records were created?
- [ ] Does the test verify that the extracted text is not empty?
- [ ] Does the integration test pass?
- [ ] Do all quality checks pass?

After completing this step, stop and request approval before proceeding to Step 12. 