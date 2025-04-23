# Step 4: Create Basic Celery Task Structure

## Goal
Define the Celery task function signature and basic logging, without OCR logic.

## TDD (RED)
Write a test in `app/tests/test_unit/test_worker.py` to verify that the task function exists, is properly decorated, and accepts the required parameters.

```python
# app/tests/test_unit/test_worker.py
import pytest
from unittest.mock import patch, MagicMock

def test_process_pdf_attachment_task_definition():
    """Test that the process_pdf_attachment task is properly defined."""
    try:
        # Import the task
        from app.worker.tasks import process_pdf_attachment
        
        # Verify it's decorated as a Celery task (check for attributes added by @shared_task)
        assert hasattr(process_pdf_attachment, 'delay'), "Task should have a 'delay' method from Celery"
        assert hasattr(process_pdf_attachment, 'apply_async'), "Task should have an 'apply_async' method from Celery"
        
        # Simulate calling the task to verify it accepts attachment_id parameter
        # Mock the actual task execution to avoid side effects
        with patch('app.worker.tasks.process_pdf_attachment.run') as mock_run:
            process_pdf_attachment(attachment_id=1)
            mock_run.assert_called_once()
            
    except ImportError:
        pytest.fail("Could not import process_pdf_attachment from app.worker.tasks")
    except Exception as e:
        pytest.fail(f"Failed to verify task definition: {e}")
```

## Implementation (GREEN)

### 1. Add Configuration Settings

First, add new configuration settings to `app/core/config.py`:

```python
# app/core/config.py
from typing import List
from pydantic import Field

class Settings:
    # ... existing settings ...

    # PDF Processing Configuration
    PDF_BATCH_COMMIT_SIZE: int = Field(
        default=10,
        description="Number of pages to process before committing. Set to 0 for single transaction per PDF."
    )
    PDF_USE_SINGLE_TRANSACTION: bool = Field(
        default=False,
        description="If True, processes entire PDF in a single transaction."
    )
    PDF_MAX_ERROR_PERCENTAGE: float = Field(
        default=10.0,
        description="Maximum percentage of pages that can fail before task fails."
    )

    # Tesseract Configuration
    TESSERACT_PATH: str = Field(
        default="/usr/local/bin/tesseract",  # Default macOS Homebrew path
        description="Path to Tesseract executable"
    )
    TESSERACT_LANGUAGES: List[str] = Field(
        default=["eng"],
        description="Languages to use for OCR"
    )
```

### 2. Create Task Definition

Create the file `app/worker/tasks.py` with the basic task structure:

```python
# app/worker/tasks.py
import logging
from celery import shared_task
from celery.exceptions import MaxRetriesExceededError, Retry
from app.core.config import settings
import time  # For simulating work

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3, default_retry_delay=60, name='app.worker.tasks.process_pdf_attachment')
def process_pdf_attachment(self, attachment_id: int) -> str:
    """
    Celery task to OCR a PDF attachment page by page.
    (Placeholder implementation)
    Args:
        self: The task instance (automatically passed with bind=True).
        attachment_id: The ID of the Attachment record to process.

    Returns:
        A status message string.
    """
    task_id = self.request.id
    logger.info(f"Task {task_id}: Received task to process attachment ID: {attachment_id}")

    # Placeholder for actual logic
    try:
        # Simulate some work
        time.sleep(1)
        logger.info(f"Task {task_id}: Placeholder processing complete for attachment {attachment_id}")
        status_message = f"Task {task_id}: Placeholder success for attachment {attachment_id}"
    except Exception as e:
        logger.error(f"Task {task_id}: Error in placeholder for attachment {attachment_id}: {e}", exc_info=True)
        try:
            raise self.retry(exc=e, countdown=int(60 * (self.request.retries + 1)))
        except MaxRetriesExceededError:
            logger.error(f"Task {task_id}: Max retries exceeded for placeholder task {attachment_id}.")
            status_message = f"Task {task_id}: Failed attachment {attachment_id} after max retries."
        except Retry:
            raise
        except Exception as retry_err:
            logger.error(f"Task {task_id}: Error during retry mechanism for {attachment_id}: {retry_err}")
            status_message = f"Task {task_id}: Failed attachment {attachment_id}, retry mechanism failed."

    return status_message
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
Run the test to verify the task has been properly defined:
```bash
pytest app/tests/test_unit/test_worker.py::test_process_pdf_attachment_task_definition
```

The test should now pass.

## Self-Verification Checklist
- [ ] Are the new PDF processing settings added to `Settings` class?
- [ ] Are the Tesseract configuration settings added to `Settings` class?
- [ ] Is the task function defined with the correct decorator?
- [ ] Does the task function have the correct signature and type hints?
- [ ] Is basic error handling and retry logic implemented?
- [ ] Do all tests pass?
- [ ] Do all quality checks pass?

After completing this step, stop and request approval before proceeding to Step 5. 