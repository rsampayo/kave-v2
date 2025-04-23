# Step 1: Add Dependencies and Basic Celery Setup

## Goal
Add required libraries and minimal Celery configuration, considering macOS dev and Heroku prod environments.

## TDD (RED)
Write a simple test to verify that the Celery app instance can be imported and created. This test will fail initially.

```python
# app/tests/test_unit/test_worker.py
import pytest
from celery import Celery

def test_celery_app_instance():
    """Test that the Celery app instance can be created."""
    try:
        # Ensure celery_app can be imported after configuration
        from app.worker.celery_app import celery_app
        assert isinstance(celery_app, Celery)
        # Check if broker URL is configured (optional but good)
        assert celery_app.conf.broker_url is not None
    except ImportError:
        pytest.fail("Could not import celery_app from app.worker.celery_app")
    except Exception as e:
        pytest.fail(f"Failed to create celery_app instance: {e}")
```

## Implementation (GREEN)

### 1. Add Dependencies

Add the following dependencies to `requirements.in`:
```
celery[redis]
pymupdf
pillow
asgiref
pytesseract
```

Regenerate the requirements files:
```bash
pip-compile requirements.in
pip-compile requirements-dev.in  # if separate
```

Commit both the updated `.in` and regenerated `.txt` files together.

### 2. Install System Dependencies

#### macOS
Install Redis and Tesseract:
```bash
brew install redis tesseract tesseract-lang
brew services start redis
```

#### Heroku
*Note:* We won't add the Heroku buildpack yet, but keep it in mind for later:
- `heroku buildpacks:add --index 1 https://github.com/heroku/heroku-buildpack-apt`
- Create an `Aptfile` with `tesseract-ocr libtesseract-dev tesseract-ocr-eng`

### 3. Update Configuration

Add Celery configuration settings to `app/core/config.py`:

```python
# In the Settings class in app/core/config.py
CELERY_BROKER_URL: str = Field(
    default="redis://localhost:6379/0",
    description="URL for the Celery broker (Redis)"
)
CELERY_RESULT_BACKEND: str = Field(
    default="redis://localhost:6379/0",
    description="URL for the Celery result backend (Redis)"
)
```

Ensure the `Settings` class correctly loads these from environment variables, prioritizing `REDIS_URL` if present (for Heroku).

### 4. Create Celery Application

Create the basic directory structure and files:

```bash
mkdir -p app/worker
touch app/worker/__init__.py
```

Create `app/worker/celery_app.py` with the following content:

```python
# app/worker/celery_app.py
from celery import Celery
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

# Determine broker and backend URLs, prioritizing Heroku's REDIS_URL if available
broker_url = getattr(settings, 'REDIS_URL', settings.CELERY_BROKER_URL)
backend_url = getattr(settings, 'REDIS_URL', settings.CELERY_RESULT_BACKEND)

if broker_url != settings.CELERY_BROKER_URL:
    logger.info(f"Using REDIS_URL from environment for Celery broker: {broker_url}")
if backend_url != settings.CELERY_RESULT_BACKEND:
     logger.info(f"Using REDIS_URL from environment for Celery backend: {backend_url}")


celery_app = Celery(
    "worker",
    broker=broker_url,
    backend=backend_url,
    include=["app.worker.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Recommended Celery settings for reliability
    task_acks_late=True,
    worker_prefetch_multiplier=1, # Process one task at a time per worker process
)

logger.info(f"Celery App '{celery_app.main}' initialized.")
logger.info(f"Broker URL: {celery_app.conf.broker_url}")
logger.info(f"Result Backend: {celery_app.conf.result_backend}")


if __name__ == "__main__":
    # This allows running the worker directly using `python -m app.worker.celery_app worker ...`
    # Though typically you run `celery -A app.worker.celery_app worker ...`
    celery_app.start()
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
Run the test to verify that the Celery app instance can be created:
```bash
pytest app/tests/test_unit/test_worker.py
```

The test should now pass.

## Self-Verification Checklist
- [ ] Do the dependencies install (`pip install -r requirements.txt`)?
- [ ] Is Redis running locally?
- [ ] Are Celery configuration variables present in `app/core/config.py`?
- [ ] Does the Celery app instance get created without errors?
- [ ] Does the test pass?
- [ ] Do all quality checks pass?

After completing this step, stop and request approval before proceeding to Step 2. 