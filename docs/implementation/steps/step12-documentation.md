# Step 12: Documentation and Heroku Preparation

## Goal
Update project documentation for the new OCR feature and add Heroku-specific deployment configurations.

## Implementation

### 1. Update README.md

Update the main README.md to include information about the new OCR feature:

```markdown
# PDF OCR Functionality

This application includes functionality to automatically extract text from PDF attachments using OCR:

## Features
- Automatic OCR processing of PDF attachments received via email webhooks
- Text extraction using PyMuPDF with Pytesseract OCR fallback for image-based PDFs
- Text storage per page in the database for easy searching and retrieval
- Asynchronous processing using Celery to avoid impacting webhook response times

## System Dependencies

### macOS Development
```bash
# Install required system dependencies
brew install tesseract tesseract-lang redis

# Start Redis for Celery
brew services start redis
```

### Heroku Deployment
The application requires additional buildpacks for Tesseract and PDF processing on Heroku:
```bash
heroku buildpacks:add --index 1 https://github.com/heroku/heroku-buildpack-apt
```

## Environment Variables
```
# Redis Configuration (Celery)
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
# Note: On Heroku, these will be overridden by REDIS_URL

# PDF Processing Configuration
PDF_BATCH_COMMIT_SIZE=10  # Set to 0 for single transaction per PDF
PDF_USE_SINGLE_TRANSACTION=false
PDF_MAX_ERROR_PERCENTAGE=10.0

# Tesseract Configuration
TESSERACT_PATH=/usr/local/bin/tesseract  # Update for your environment
TESSERACT_LANGUAGES=eng  # Comma-separated list of language codes
```

## Starting the Celery Worker
```bash
# Development
celery -A app.worker.celery_app worker -l info

# On Heroku, the worker is defined in the Procfile
```
```

### 2. Create Aptfile for Heroku

Create an `Aptfile` in the root directory of the project:

```
# Aptfile

# OCR Dependencies
tesseract-ocr
libtesseract-dev
tesseract-ocr-eng

# PyMuPDF Dependencies
libmupdf-dev
libmupdf1.18  # Version may vary
libfreetype6-dev
libjpeg-dev
libjbig2dec0
libopenjp2-7
libxext6

# Additional dependencies that might be needed
poppler-utils
```

### 3. Update Procfile for Heroku

Update or create the `Procfile` in the root directory to include a worker process:

```
# Procfile
web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
release: alembic upgrade head
worker: celery -A app.worker.celery_app worker --loglevel=info
```

### 4. Add Comprehensive API Documentation

Add detailed docstrings to enhance the API documentation:

#### 4.1. AttachmentTextContent Model

Update the `AttachmentTextContent` class docstring:

```python
class AttachmentTextContent(Base):
    """
    Stores OCR-extracted text content from PDF attachments, page by page.

    This model maintains a one-to-many relationship with the Attachment model,
    where each record represents the text content of a single page from a PDF attachment.
    Text is extracted using direct PDF text extraction (via PyMuPDF) with OCR fallback
    (via Tesseract) when direct extraction yields minimal text.

    Attributes:
        id (int): Primary key.
        attachment_id (int): Foreign key to the parent Attachment.
        page_number (int): 1-based page number within the PDF.
        text_content (str): Extracted text content from the page. May be NULL if extraction failed.
        attachment (Attachment): Relationship to the parent Attachment model.
    """
```

#### 4.2. OCR Task Function

Update the `process_pdf_attachment` function docstring:

```python
@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_pdf_attachment(self, attachment_id: int) -> str:
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
```

#### 4.3. AttachmentService Method

Update the `process_attachments` method docstring:

```python
async def process_attachments(
    self, email_id: int, attachment_data: list[dict]
) -> list[Attachment]:
    """
    Process and store email attachments, triggering OCR for PDF attachments.
    
    This method:
    1. Decodes base64 attachment content
    2. Creates an Attachment record
    3. Stores the file in the storage service
    4. For PDF attachments, dispatches an OCR task to extract and store text
    
    Args:
        email_id: The ID of the parent Email
        attachment_data: List of attachment data dictionaries
        
    Returns:
        List of created Attachment objects
    """
```

### 5. Update Contributing Guide (if applicable)

If your project has a CONTRIBUTING.md file, update it to include:

```markdown
## PDF OCR Development

When working with the PDF OCR feature:

1. **System Dependencies**: Ensure you have Redis and Tesseract installed locally.
2. **Running the Worker**: Start the Celery worker to process OCR tasks:
   ```bash
   celery -A app.worker.celery_app worker -l info
   ```
3. **Testing**: 
   - Unit tests for OCR are in `app/tests/test_unit/test_worker.py`
   - Integration tests are in `app/tests/test_integration/test_api/test_pdf_ocr_flow.py`
   - Tests use Celery's eager mode to run tasks synchronously

4. **Configuration**:
   - Adjust OCR settings in environment variables (see README)
   - For additional language support, install language packs:
     ```bash
     brew install tesseract-lang  # macOS
     ```
     and update the `TESSERACT_LANGUAGES` environment variable.
```

### 6. Document Heroku Setup Steps

Create a `docs/deployment/heroku.md` file with detailed Heroku deployment instructions:

```markdown
# Heroku Deployment for PDF OCR

To deploy the application with PDF OCR capability to Heroku, follow these additional steps:

## 1. Add Required Buildpacks

```bash
# Add the apt buildpack to install system dependencies
heroku buildpacks:add --index 1 https://github.com/heroku/heroku-buildpack-apt

# Make sure the Python buildpack is also present
heroku buildpacks:add heroku/python
```

## 2. Configure Redis

```bash
# Add the Redis add-on for Celery
heroku addons:create heroku-redis:hobby-dev
```

## 3. Configure Environment Variables

```bash
# PDF Processing Configuration
heroku config:set PDF_BATCH_COMMIT_SIZE=10
heroku config:set PDF_USE_SINGLE_TRANSACTION=false
heroku config:set PDF_MAX_ERROR_PERCENTAGE=10.0

# Tesseract Configuration
heroku config:set TESSERACT_PATH=/app/.apt/usr/bin/tesseract
heroku config:set TESSERACT_LANGUAGES=eng
```

## 4. Scale Workers

After deploying, scale the Celery worker dyno:

```bash
heroku ps:scale worker=1
```

## 5. Monitoring

Monitor your Celery workers:

```bash
# View worker logs
heroku logs --tail --dyno worker

# Check dyno status
heroku ps
```

## 6. Troubleshooting

If OCR is not working properly:

1. Check if the worker process is running: `heroku ps`
2. Examine worker logs: `heroku logs --tail --dyno worker`
3. Verify system dependencies were installed: `heroku run ls -la /app/.apt/usr/bin/tesseract`
4. Test OCR manually: `heroku run python -c "import pytesseract; print(pytesseract.get_tesseract_version())"`
```

## Quality Check
Run the following code quality tools on any new documentation code examples:
```bash
black .
isort .
flake8 .
mypy app
```

Also, ensure that all documentation:
- Is clear and concise
- Includes all necessary details for setup and configuration
- Follows the project's existing documentation style
- Has no spelling or grammatical errors

## Testing
Verify that the documentation is correct by following the instructions for at least:
- Configuring and starting the Celery worker locally
- Setting up the proper environment variables

## Self-Verification Checklist
- [ ] Is the README.md updated with OCR feature information?
- [ ] Are system dependencies (Tesseract, Redis) clearly documented?
- [ ] Are environment variables for the OCR feature documented?
- [ ] Is the `Aptfile` created with necessary dependencies for Heroku?
- [ ] Is the `Procfile` updated to include the Celery worker?
- [ ] Are docstrings added to `AttachmentTextContent` model?
- [ ] Are docstrings added to `process_pdf_attachment` task?
- [ ] Are docstrings added to `AttachmentService.process_attachments`?
- [ ] Is the contributing guide updated (if applicable)?
- [ ] Are Heroku deployment instructions documented?
- [ ] Is all documentation clear, concise, and free of errors?

This completes the implementation of the PDF OCR feature for email attachments. The feature now extracts text from PDF attachments, stores it in the database, and is fully documented for both development and deployment. 