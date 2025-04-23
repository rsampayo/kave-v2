

**AI Assistant Task: Implement PDF OCR for Email Attachments (macOS Dev / Heroku Prod)**

**IMPORTANT WORKFLOW INSTRUCTIONS:**
* IMPLEMENT ONLY ONE STEP AT A TIME. After completing a step, STOP and ask for permission before proceeding to the next step.
* Each step should be fully implemented, tested, and verified before moving on.
* Clearly indicate which step you've completed and wait for explicit approval before starting the next one.
* If anything is unclear, ask for clarification before proceeding.

**Overall Goal:** Add functionality to OCR PDF attachments received via email webhooks using Celery, PyMuPDF, and Pytesseract (as fallback). Store the extracted text per page in a new database table. Deployable on Heroku.

**Mandatory Guidelines:** Strictly follow the provided "Development Guidelines" document, including:
*   **TDD:** Red-Green-Refactor cycle for all code.
*   **Iterative Quality:** Run Black, isort, Flake8, MyPy frequently and fix issues immediately.
*   **Minimal Changes:** Only implement the changes required for the current step.
*   **Testing:** Ensure all tests pass before moving to the next step.
*   **Dependencies:** Use `pip-compile` via `requirements.in`.
*   **Migrations:** Use Alembic.

---

**Step 1: Add Dependencies and Basic Celery Setup**

*   **Goal:** Add required libraries and minimal Celery configuration, considering macOS dev and Heroku prod.
*   **TDD:** RED - Write a simple test (e.g., `app/tests/test_unit/test_worker.py`) to verify that the Celery app instance can be imported and created. This test will fail initially.
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
*   **Action (GREEN):**
    1.  Add `celery[redis]`, `pymupdf`, `pillow`, `asgiref`, and `pytesseract` to `requirements.in`. *Note: `pytesseract` requires `pillow`.*
    2.  Run `pip-compile requirements.in` and `pip-compile requirements-dev.in` (if separate). Commit the changes to both `.in` and `.txt` files.
    3.  **Local Dev (macOS):** Ensure Redis is installed (`brew install redis`) and running (`brew services start redis`).
    4.  Add `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND` to `app/core/config.py -> Settings`. Use Redis defaults for local dev (e.g., `redis://localhost:6379/0`). **Important:** Ensure the `Settings` class correctly loads these from environment variables, as Heroku will provide its own Redis URL (e.g., `REDIS_URL`). The config should prioritize `REDIS_URL` if present.
    5.  Create the directory `app/worker/`.
    6.  Create `app/worker/__init__.py`.
    7.  Create `app/worker/celery_app.py` with the following minimal content:
        ```python
        # app/worker/celery_app.py
        from celery import Celery
        from app.core.config import settings
        import logging

        logger = logging.getLogger(__name__)

        # Determine broker and backend URLs, prioritizing Heroku's REDIS_URL if available
        # (Assuming settings has logic like: broker = os.getenv('REDIS_URL', settings.CELERY_BROKER_URL))
        # If not, add logic here or in settings.py
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
    8.  **System Dependency (Tesseract):**
        *   **macOS:** Install Tesseract: `brew install tesseract tesseract-lang` (Installs English + support for other languages).
        *   **Heroku:** *Acknowledge* that a Tesseract buildpack will be needed later. We won't add it yet, but keep it in mind for documentation/deployment. (e.g., `heroku buildpacks:add --index 1 https://github.com/heroku/heroku-buildpack-apt` then create an `Aptfile` with `tesseract-ocr libtesseract-dev tesseract-ocr-eng`).
*   **Quality Check (REFACTOR):** Run `black .`, `isort .`, `flake8 .`, `mypy app`. Fix any reported issues.
*   **Test (REFACTOR):** Run `pytest app/tests/test_unit/test_worker.py`. The test should now pass.
*   **(Self-Verification):** Do the dependencies install (`pip install -r requirements.txt`)? Is Redis running locally? Are config variables present? Does the Celery app instance get created without errors? Does the test pass? Do quality checks pass?

---

**Step 2: Define `AttachmentTextContent` Model & Relationship**

*   **Goal:** Create the SQLAlchemy model structure for storing OCR results.
*   **TDD:** RED - Write a failing test in `app/tests/test_unit/test_models_documentation.py` (or a new `test_models.py`) named `test_attachment_text_content_model`. This test should attempt to import `AttachmentTextContent`, instantiate it with dummy data (e.g., `attachment_id=1`, `page_number=1`, `text_content='test'`), and assert its attributes are set correctly. It will fail because the model doesn't exist. Also, test that an `Attachment` instance now has a `text_contents` attribute (which will initially fail).
*   **Action (GREEN):**
    1.  Create `app/models/attachment_text_content.py` with the `AttachmentTextContent` SQLAlchemy model definition as outlined in the plan (including `id`, `attachment_id` ForeignKey, `page_number`, `text_content`, and the relationship back to `Attachment`). Use `Text` for `text_content` and make it nullable. Include necessary imports (`SQLAlchemy`, `Mapped`, `mapped_column`, `ForeignKey`, `relationship`, `Base`, `TYPE_CHECKING`, `Attachment`).
    2.  Update `app/models/__init__.py` to import and expose `AttachmentTextContent`.
    3.  In `app/models/email_data.py`, add the one-to-many relationship to the `Attachment` model:
        ```python
        # Inside Attachment class in app/models/email_data.py
        # Add TYPE_CHECKING import for AttachmentTextContent if needed at the top
        from typing import TYPE_CHECKING, List # Ensure List is imported
        if TYPE_CHECKING:
             from app.models.attachment_text_content import AttachmentTextContent

        # Make sure the type hint uses List[]
        text_contents: Mapped[List["AttachmentTextContent"]] = relationship(
            "AttachmentTextContent", back_populates="attachment", cascade="all, delete-orphan"
        )
        ```
*   **Quality Check (REFACTOR):** Run `black .`, `isort .`, `flake8 .`, `mypy app`. Fix any reported issues.
*   **Test (REFACTOR):** Run `pytest`. The tests written in the RED step should now pass.
*   **(Self-Verification):** Does the model file exist? Does the model have the correct columns, types, and relationships? Is the relationship added to `Attachment`? Do the tests pass? Do quality checks pass?

---

**Step 3: Generate & Apply Database Migration**

*   **Goal:** Update the database schema to include the new `attachment_text_content` table.
*   **TDD:** Not directly applicable for migration *generation*. We will rely on subsequent tests requiring the schema.
*   **Action:**
    1.  Run `alembic revision --autogenerate -m "Add AttachmentTextContent model"` in your terminal.
    2.  **Crucially, review** the generated migration script in `alembic/versions/`. Verify it correctly creates the `attachment_text_content` table with all specified columns (`id`, `attachment_id`, `page_number`, `text_content`), the foreign key constraint to `attachments.id` with `ondelete="CASCADE"`, and necessary indexes.
    3.  Run `alembic upgrade head` to apply the migration to your local development PostgreSQL database.
*   **Quality Check:** Manual review of the migration script.
*   **Test:** No automated test for this step, verify by inspecting the database schema if necessary (e.g., using `psql` or a GUI tool).
*   **(Self-Verification):** Did Alembic generate a migration script? Does the script look correct? Did `alembic upgrade head` run without errors on your local PG database? Does the `attachment_text_content` table exist in your database?

---

**Step 4: Create Basic Celery Task Structure**

*   **Goal:** Define the Celery task function signature and basic logging, without OCR logic.
*   **TDD:** RED - Write a test in `app/tests/test_unit/test_worker.py` named `test_process_pdf_attachment_task_definition`. Use `unittest.mock.patch` to mock `celery.shared_task` if needed, or simply try importing the task function. Verify the function `process_pdf_attachment` exists in `app.worker.tasks`, is decorated as a Celery task, and accepts `attachment_id` as an argument.

*   **Action (GREEN):**
    1.  First, add new configuration settings to `app/core/config.py`:
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

    2.  Create the file `app/worker/tasks.py` with the basic task structure:
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

*   **Quality Check (REFACTOR):** Run `black .`, `isort .`, `flake8 .`, `mypy app`. Fix issues.
*   **Test (REFACTOR):** Run `pytest`. The tests should pass.
*   **(Self-Verification):** Are the new settings added to `Settings`? Is the task function defined with correct signature and type hints? Do tests pass? Do quality checks pass?

---

**Step 5: Implement Task: Fetch Attachment & PDF Data**

*   **Goal:** Add logic to the Celery task to fetch the `Attachment` record and retrieve its PDF data from storage using `StorageService`. Handle errors if the attachment or its data isn't found.
*   **TDD:** RED - Update `test_process_pdf_attachment_task_call` (or create a new test like `test_process_pdf_attachment_data_fetching`).
    *   Use `unittest.mock.patch` to mock `app.worker.tasks.get_session` (or `app.db.session.get_session`).
    *   Mock the returned session object (e.g., `mock_session.get.return_value = mock_attachment` or `None`). **Note:** Since Celery tasks often run synchronously, you might mock a *synchronous* session and its methods here for unit testing the task logic itself.
    *   Mock `app.worker.tasks.StorageService`. Mock its `get_file` method. Since `get_file` is async, you'll need `AsyncMock` and ensure the task code correctly bridges async/sync (by mocking `async_to_sync`). `mock_storage_instance.get_file = AsyncMock(return_value=b'pdfbytes')` or `None`.
    *   Test the scenario where the attachment is found and `storage.get_file` returns data.
    *   Test the scenario where the attachment is *not* found (`db.get` returns `None`). Assert appropriate logging occurs and the task returns a specific failure message.
    *   Test the scenario where the attachment has no `storage_uri`. Assert logging and return failure message.
    *   Test the scenario where the attachment is found but `storage.get_file` returns `None`. Assert appropriate logging and return failure message.
*   **Action (GREEN):**
    1.  Add imports to `app/worker/tasks.py`: `get_session` from `app.db.session` (choose sync or async carefully), `StorageService` from `app.services.storage_service`, `Attachment` from `app.models.email_data`, `from asgiref.sync import async_to_sync`.
    2.  Implement the logic *inside* the `try` block of `process_pdf_attachment`:
        ```python
        # Inside process_pdf_attachment task...
        task_id = self.request.id # Get task ID for logging
        logger.info(f"Task {task_id}: Starting OCR process for attachment ID: {attachment_id}")

        db = None # Initialize db to None for finally block safety
        try:
            # Assuming a synchronous session helper for standard Celery workers
            # Adapt if using async workers or event loops within tasks.
            from app.db.session import get_session as get_sync_session
            db = get_sync_session() # Get a SYNC session

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
*   **Quality Check (REFACTOR):** Run `black .`, `isort .`, `flake8 .`, `mypy app`. Fix issues.
*   **Test (REFACTOR):** Run `pytest`. The updated tests should pass.
*   **(Self-Verification):** Does the task get a DB session? Does it fetch the `Attachment` using `db.get`? Does it check for `storage_uri`? Does it instantiate `StorageService`? Does it call `async_to_sync(storage.get_file)(...)` instead of using `asyncio.run`? Does it handle `pdf_data` being `None`? Does it handle exceptions during fetch? Is the session closed in `finally`? Do tests pass? Do quality checks pass?

---

**Step 6: Implement Task: Basic PyMuPDF Parsing (Page Count)**

*   **Goal:** Add PyMuPDF logic to open the retrieved PDF data and log the page count.
*   **TDD:** RED - Update the task test (`test_process_pdf_attachment_data_fetching` or similar).
    *   Ensure the mock `storage.get_file` (via `asyncio.run` mock if needed) returns valid PDF bytes (can be minimal).
    *   Use `unittest.mock.patch` to mock `app.worker.tasks.fitz`. Mock the `fitz.open` method.
    *   Mock the returned `Document` object (e.g., `mock_doc = MagicMock()`). Set its `page_count` attribute (e.g., `mock_doc.page_count = 3`). Make `fitz.open.return_value = mock_doc`.
    *   Assert that `fitz.open` is called with `stream=pdf_data, filetype='pdf'`.
    *   Assert that `doc.page_count` is accessed and logged.
    *   Add a test case where `fitz.open` raises an exception (e.g., `fitz.FitzError`). Assert appropriate logging and that the task maybe retries or returns a failure status.
*   **Action (GREEN):**
    1.  Add `import fitz` to `app/worker/tasks.py`.
    2.  Inside the `try` block of `process_pdf_attachment`, *after* successfully getting `pdf_data`, add the PDF opening logic:
        ```python
        # Inside the main try block, after pdf_data is confirmed...
        doc = None # Initialize doc
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
*   **Quality Check (REFACTOR):** Run `black .`, `isort .`, `flake8 .`, `mypy app`. Fix issues.
*   **Test (REFACTOR):** Run `pytest`. The updated tests should pass.
*   **(Self-Verification):** Is `fitz` imported? Is `fitz.open` called correctly? Is the page count logged? Is the exception during `fitz.open` handled? Do tests pass? Do quality checks pass?

---

**Step 7: Implement Task: Loop & Direct Text Extraction & DB Save**

*   **Goal:** Loop through the PDF pages, extract text directly using `page.get_text()`, and save each page's text to the `AttachmentTextContent` table.
*   **TDD:** RED - Update the task test.
    *   Mock `doc.load_page`. Make it return a mock page object (`mock_page = MagicMock()`).
    *   Mock `mock_page.get_text`. Make it return sample text (e.g., `f"Text from page {page_num + 1}"`).
    *   Mock the database session's `add` and `commit` methods (`mock_session.add = MagicMock()`, `mock_session.commit = MagicMock()` - assuming sync session for task).
    *   Mock `db.rollback` as well.
    *   Assert that the code loops `doc.page_count` times.
    *   Assert `doc.load_page` is called for each page number.
    *   Assert `page.get_text("text")` is called for each page.
    *   Assert `db.add` is called for each page with an `AttachmentTextContent` instance containing the correct `attachment_id`, `page_number` (1-based), and the mocked `text_content`.
    *   Assert `db.commit()` is called periodically (if implemented) and/or at the end.
    *   Add test cases for both transaction modes (single transaction and batched commits).
    *   Add test cases for error threshold checking.
    *   Add a test case where `page.get_text()` or `db.add()` raises an exception within the loop. Assert `db.rollback()` is called and the loop potentially continues or the task fails/retries appropriately.
*   **Action (GREEN):**
    1.  Add `from app.models.attachment_text_content import AttachmentTextContent` import.
    2.  Replace the placeholder comment `# --- Page processing logic will go here ---` with the following loop structure inside the `try` block where `doc` is available:
        ```python
        # Inside the main try block, after doc is created and page count logged
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

                        # --- OCR Fallback logic will go here (Step 8) ---
                        page_text_to_save = page_text  # Use direct text for now

                        # Create and Save AttachmentTextContent record
                        text_content_entry = AttachmentTextContent(
                            attachment_id=attachment_id,
                            page_number=page_num + 1,  # Page numbers are 1-based
                            text_content=page_text_to_save.strip() if page_text_to_save else None
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

                    # --- OCR Fallback logic will go here (Step 8) ---
                    page_text_to_save = page_text  # Use direct text for now

                    # Create and Save AttachmentTextContent record
                    text_content_entry = AttachmentTextContent(
                        attachment_id=attachment_id,
                        page_number=page_num + 1,  # Page numbers are 1-based
                        text_content=page_text_to_save.strip() if page_text_to_save else None
                    )
                    db.add(text_content_entry)
                    page_commit_counter += 1
                    processed_pages += 1
                    logger.debug(f"Task {task_id}: Added page {page_num + 1}/{total_pages} content for attachment {attachment_id}")

                    # Commit periodically if batch size is set
                    if settings.PDF_BATCH_COMMIT_SIZE > 0 and page_commit_counter >= settings.PDF_BATCH_COMMIT_SIZE:
                        db.commit()  # Use sync commit
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
                db.commit()  # Use sync commit
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
*   **Quality Check (REFACTOR):** Run `black .`, `isort .`, `flake8 .`, `mypy app`. Fix issues.
*   **Test (REFACTOR):** Run `pytest`. The updated tests should pass.
*   **(Self-Verification):** Does the code handle both transaction modes correctly? Is the error threshold check implemented? Does the code loop through pages? Is `get_text` called? Are `AttachmentTextContent` objects created correctly? Is `db.add` called per page? Is `db.commit` called according to the selected strategy? Is `db.rollback` called on page error? Do tests pass? Do quality checks pass?

---

**Step 8: Implement Task: Pytesseract OCR Fallback**

*   **Goal:** Enhance the page processing loop to use `pytesseract` OCR if `page.get_text()` returns minimal text.
*   **TDD:** RED - Update the task test.
    *   Add test scenarios where the mocked `page.get_text` returns very short text (e.g., `"   "` or `"\n"`).
    *   Use `unittest.mock.patch` to mock `app.worker.tasks.pytesseract`. Mock `pytesseract.image_to_string`. Make it return specific OCR text.
    *   Mock `page.get_pixmap` to return a mock pixmap object (`mock_pix = MagicMock()`).
    *   Mock `mock_pix.tobytes`. Make it return dummy image bytes (e.g., `b'png_bytes'`).
    *   Use `unittest.mock.patch` to mock `app.worker.tasks.Image`. Mock `Image.open`. Make it return a mock image object.
    *   Assert that `page.get_pixmap`, `pix.tobytes`, `Image.open`, and `pytesseract.image_to_string` are called *only* when `get_text` result is short.
    *   Assert that the text saved to the DB comes from `image_to_string` in this fallback case.
    *   Add test cases for different Tesseract configurations (path and languages).
    *   Add a test case where `pytesseract.image_to_string` raises an error (e.g., `pytesseract.TesseractNotFoundError` or a generic `Exception`). Assert that the original (short) text from `get_text` is still saved and a warning is logged.
*   **Action (GREEN):**
    1.  Add imports: `import pytesseract`, `from PIL import Image`, `import io`.
    2.  Inside the page processing loop (`for page_num...`), modify the text extraction part:
        ```python
            # Inside the page loop's try block (replace previous text extraction)
            page = doc.load_page(page_num)
            direct_text = page.get_text("text") or ""  # Direct text extraction, ensure string

            page_text_to_save = direct_text  # Default to direct extraction

            # OCR Fallback Logic
            TEXT_LENGTH_THRESHOLD = 50  # Chars; Tune this threshold
            if len(direct_text.strip()) < TEXT_LENGTH_THRESHOLD:
                logger.info(f"Task {task_id}: Page {page_num+1} has little direct text ({len(direct_text.strip())} chars), attempting OCR.")
                try:
                    # Configure Tesseract path from settings
                    pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_PATH

                    # Render page to an image (e.g., PNG) at higher DPI for better OCR
                    zoom = 4  # zoom factor 4 => 300 DPI (approx)
                    mat = fitz.Matrix(zoom, zoom)
                    pix = page.get_pixmap(matrix=mat, alpha=False)  # alpha=False for non-transparent image

                    img_data = pix.tobytes("png")  # Use PNG format

                    if not img_data:
                        logger.warning(f"Task {task_id}: Failed to get image bytes for page {page_num+1}.")
                    else:
                        img = Image.open(io.BytesIO(img_data))

                        # Perform OCR using configured languages
                        ocr_text = pytesseract.image_to_string(
                            img,
                            lang="+".join(settings.TESSERACT_LANGUAGES)
                        )

                        if ocr_text.strip():  # Only use OCR text if it's not empty
                            page_text_to_save = ocr_text
                            logger.info(
                                f"Task {task_id}: OCR successful for page {page_num+1}, "
                                f"length: {len(ocr_text)}, "
                                f"languages: {'+'.join(settings.TESSERACT_LANGUAGES)}"
                            )
                        else:
                            logger.warning(
                                f"Task {task_id}: OCR produced no text for page {page_num+1}, "
                                f"keeping direct text (length: {len(direct_text)})"
                            )

                except ImportError:
                    logger.error(
                        f"Task {task_id}: Pytesseract or Pillow not installed. "
                        f"Cannot perform OCR fallback. Path: {settings.TESSERACT_PATH}"
                    )
                    # Sticks with direct_text
                except pytesseract.TesseractNotFoundError:
                    logger.error(
                        f"Task {task_id}: Tesseract executable not found at {settings.TESSERACT_PATH}. "
                        "Ensure it's installed and path is correct."
                    )
                    # Sticks with direct_text
                except Exception as ocr_err:
                    # Catch other potential errors (PIL issues, tesseract runtime errors)
                    logger.warning(
                        f"Task {task_id}: OCR failed for page {page_num+1} of attachment {attachment_id}: {ocr_err}",
                        exc_info=True
                    )
                    # Sticks with direct_text (which is already in page_text_to_save)

            # Create DB entry using page_text_to_save
            text_content_entry = AttachmentTextContent(
                attachment_id=attachment_id,
                page_number=page_num + 1,
                text_content=page_text_to_save.strip() if page_text_to_save else None
            )
            db.add(text_content_entry)
            page_commit_counter += 1
            processed_pages += 1  # Count success here now
            logger.debug(
                f"Task {task_id}: Added page {page_num + 1}/{doc.page_count} content "
                f"(OCR {'used' if page_text_to_save != direct_text else 'not needed'}) "
                f"for attachment {attachment_id}"
            )

            # (rest of the loop: periodic commit logic...)
        ```
*   **Quality Check (REFACTOR):** Run `black .`, `isort .`, `flake8 .`, `mypy app`. Fix issues. Ensure necessary libraries (`pytesseract`, `PIL`, `io`) are imported.
*   **Test (REFACTOR):** Run `pytest`. The updated tests should pass. Ensure you have tests covering the OCR path and the non-OCR path, including OCR errors and different Tesseract configurations.
*   **(Self-Verification):** Are `pytesseract`, `PIL`, `io` imported? Is the length check implemented? Is Tesseract configured from settings? Are languages configured from settings? Is `page.get_pixmap`, `Image.open`, `pytesseract.image_to_string` called conditionally? Is the OCR result used only if not empty? Are OCR errors handled gracefully (using direct text)? Do tests pass? Do quality checks pass?

---

**Step 9: Implement Task: Final Error Handling & Retries**

*   **Goal:** Ensure the Celery task's overall error handling, database rollback, Celery retries, and session closing are correctly implemented around the complete PDF processing logic.
*   **TDD:** RED - Review and enhance the task tests focusing on the outer `try...except...finally` block.
    *   Simulate exceptions occurring *before* the page loop (e.g., during PDF open) and *after* the page loop (e.g., during final commit).
    *   Verify that `db.rollback()` is called in the main `except Exception` block if `db` session exists.
    *   Verify that `self.retry(exc=e)` is called correctly.
    *   Verify `MaxRetriesExceededError` is handled and logs appropriately.
    *   Verify `db.close()` is always called in the `finally` block if `db` was successfully created.
*   **Action (GREEN):**
    1.  Review and refine the main `try...except Retry...except Exception...finally` block in `app/worker/tasks.py -> process_pdf_attachment` to ensure it correctly handles errors from all stages (data fetch, PDF open, page processing loop, commits) and manages retries and session cleanup reliably. The structure implemented in Step 7 and refined in Step 5 should largely cover this, but double-check the flow. Ensure rollback happens before retry attempts if database changes might have been staged.
        ```python
        # Refined structure (ensure this matches your implementation)
        @shared_task(bind=True, max_retries=3, default_retry_delay=60, name='app.worker.tasks.process_pdf_attachment')
        def process_pdf_attachment(self, attachment_id: int) -> str:
            task_id = self.request.id
            logger.info(f"Task {task_id}: Starting OCR task for attachment ID: {attachment_id}")
            db = None
            try:
                # 1. Get Session
                from app.db.session import get_session as get_sync_session
                db = get_sync_session()

                # 2. Fetch Attachment & PDF Data (raise exceptions on failure here)
                # ... includes async_to_sync(storage.get_file)(...) ...
                # ... handle not found, no URI, no pdf_data by raising to trigger retry ...
                attachment = db.get(Attachment, attachment_id)
                if not attachment or not attachment.storage_uri:
                     raise ValueError(f"Attachment {attachment_id} invalid or missing URI.") # Make it retryable
                storage = StorageService()
                pdf_data = async_to_sync(storage.get_file)(attachment.storage_uri)
                if not pdf_data:
                     raise ValueError(f"PDF data not found for {attachment_id} at {attachment.storage_uri}") # Make it retryable

                # 3. Open PDF
                doc = fitz.open(stream=pdf_data, filetype="pdf") # Can raise Exception

                # 4. Process Pages (Loop)
                page_commit_counter = 0
                processed_pages = 0
                errors_on_pages = 0
                # db.begin() # If using explicit transactions

                for page_num in range(doc.page_count):
                    try:
                        # ... (Page processing logic with OCR fallback) ...
                        page_text_to_save = ... # Get text
                        text_content_entry = AttachmentTextContent(...)
                        db.add(text_content_entry)
                        page_commit_counter += 1
                        processed_pages += 1
                        # ... (Periodic commit logic) ...
                        if page_commit_counter >= 10:
                            db.commit()
                            page_commit_counter = 0
                    except Exception as page_err:
                        errors_on_pages += 1
                        logger.error(f"Task {task_id}: Error on page {page_num + 1} for {attachment_id}: {page_err}", exc_info=False) # Avoid verbose stack in loop
                        db.rollback() # Rollback current batch
                        page_commit_counter = 0
                        # Continue to next page

                # 5. Final Commit
                if page_commit_counter > 0:
                    db.commit()

                # 6. Construct Success Message
                status_msg = f"Task {task_id}: Attachment {attachment_id} processed. Pages: {doc.page_count}, Success: {processed_pages}, Errors: {errors_on_pages}."
                logger.info(status_msg)
                return status_msg

            except Retry:
                # Let Celery handle Retry exceptions
                raise
            except Exception as e:
                # Handle all other exceptions for retry logic
                logger.error(f"Task {task_id}: Failed processing attachment {attachment_id}: {e}", exc_info=True)
                if db: # Ensure db session exists before trying to rollback
                    try:
                        db.rollback()
                        logger.info(f"Task {task_id}: Database transaction rolled back for failed task.")
                    except Exception as rb_err:
                        logger.error(f"Task {task_id}: Failed to rollback transaction: {rb_err}")
                # Retry logic
                try:
                    logger.warning(f"Task {task_id}: Retrying task for {attachment_id} due to error.")
                    # Pass the original exception to retry
                    raise self.retry(exc=e, countdown=int(60 * (self.request.retries + 1)))
                except MaxRetriesExceededError:
                    logger.error(f"Task {task_id}: Max retries exceeded for {attachment_id}. Giving up.")
                    return f"Task {task_id}: Failed attachment {attachment_id} after max retries."
                except Retry:
                    raise # Re-raise Retry if self.retry raised it
                except Exception as retry_err:
                     logger.error(f"Task {task_id}: Error during retry mechanism for {attachment_id}: {retry_err}")
                     return f"Task {task_id}: Failed attachment {attachment_id}, could not retry."
            finally:
                # 7. Ensure session is closed
                if db:
                    db.close()
                    logger.debug(f"Task {task_id}: Database session closed.")

        ```
*   **Quality Check (REFACTOR):** Run `black .`, `isort .`, `flake8 .`, `mypy app`. Fix issues.
*   **Test (REFACTOR):** Run `pytest`. The updated tests covering errors, rollback, retries, and `db.close` should pass.
*   **(Self-Verification):** Is the main logic wrapped correctly? Does the main `except Exception` block call `db.rollback()` (if `db` exists)? Does it call `self.retry(exc=e)`? Is `MaxRetriesExceededError` handled? Is `db.close()` called in `finally` (if `db` exists)? Do tests pass? Do quality checks pass?

---

**Step 10: Trigger Task from AttachmentService**

*   **Goal:** Modify `AttachmentService.process_attachments` to dispatch the `process_pdf_attachment` Celery task when a PDF attachment is successfully saved.
*   **TDD:** RED - Write/update tests for `app/tests/test_unit/test_services/test_attachment_service.py -> TestAttachmentService`.
    *   Use `unittest.mock.patch` to mock `app.services.attachment_service.process_pdf_attachment.delay`.
    *   Provide sample attachment data to `process_attachments`, including one PDF and one non-PDF.
    *   Ensure the mocked DB session allows the attachment object to get an ID after `add` and `flush` (e.g., `mock_db_session.flush = AsyncMock()`, manually set `attachment.id = 1` on the mocked attachment object *after* `add` is called in the test).
    *   Assert that `process_pdf_attachment.delay` is called *only once* (for the PDF).
    *   Assert it's called with the correct keyword argument (`attachment_id=X`, where X is the ID of the saved PDF attachment).
    *   Assert it's called *after* the attachment has been saved to storage (mock `storage.save_file` to confirm call order if necessary) and *after* `db.flush` has been successfully called for that attachment.
*   **Action (GREEN):**
    1.  Modify `app/services/attachment_service.py -> AttachmentService.process_attachments`.
    2.  Import the task: `from app.worker.tasks import process_pdf_attachment`.
    3.  Inside the loop, *after* the `storage_uri` has been successfully set and *after* adding the attachment to the session:
        ```python
        # Inside process_attachments loop, after storage_uri is set...
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
            result.append(attachment) # Still append to results, but skip OCR
            continue # Continue to the next attachment in the loop

        # Check if attachment ID was populated (should be after successful flush)
        if attachment.id is None:
             logger.error(f"Attachment {attachment.filename} did not get an ID after flush, cannot dispatch OCR task.")
             result.append(attachment)
             continue

        # Check if it's a PDF and dispatch the task
        is_pdf = attachment.content_type == 'application/pdf' or \
                 (attachment.filename and attachment.filename.lower().endswith('.pdf'))

        if is_pdf:
            try:
                logger.info(f"Dispatching OCR task for PDF attachment ID: {attachment.id}, Filename: {attachment.filename}")
                # Ensure attachment_id is passed correctly as a keyword argument
                process_pdf_attachment.delay(attachment_id=attachment.id)
            except Exception as dispatch_err:
                # Log error if task dispatch fails, but don't necessarily fail the request
                logger.error(f"Failed to dispatch Celery OCR task for attachment {attachment.id}: {dispatch_err}")

        result.append(attachment) # Append attachment to result list
        ```
*   **Quality Check (REFACTOR):** Run `black .`, `isort .`, `flake8 .`, `mypy app`. Fix issues.
*   **Test (REFACTOR):** Run `pytest`. The updated `AttachmentService` tests should pass.
*   **(Self-Verification):** Is the task imported? Is the PDF check correct? Is `await self.db.flush([attachment])` called before dispatch? Is `.delay()` called with the correct `attachment_id` only for PDFs? Is the task dispatch failure handled gracefully? Do tests pass? Do quality checks pass?

---

**Step 11: Integration Testing**

*   **Goal:** Verify the end-to-end flow from webhook reception to OCR text being saved in the database.
*   **TDD:** RED - Write an integration test in `app/tests/test_integration/test_api/` (e.g., `test_pdf_ocr_flow.py`).
    *   Use the `async_client` and `db_session` fixtures.
    *   Create a test webhook payload (`create_test_webhook_payload` helper) that includes a small, *real* PDF file's content, base64 encoded (you might need a small sample PDF in your test data).
    *   Configure Celery for *eager execution* during tests. Add `task_always_eager = True` to your `pytest.ini` or `pyproject.toml [tool.pytest.ini_options]`.
    *   When mocking the task's storage access in eager mode, correctly mock `async_to_sync` rather than `asyncio.run`.
    *   Send the payload to the webhook endpoint (`/v1/webhooks/mandrill`). Use appropriate headers (e.g., signature if needed, mocked).
    *   Assert the API response is successful (e.g., 202 Accepted).
    *   Query the test database (using the `db_session` fixture from your test) to:
        *   Verify the `Email` record was created.
        *   Verify the `Attachment` record was created with a `storage_uri`. Get its `id`.
        *   Verify that `AttachmentTextContent` records were created for the fetched `attachment_id` and the expected number of pages from your test PDF.
        *   Assert that the extracted `text_content` in the `AttachmentTextContent` records is not empty and potentially contains expected keywords from your test PDF.
*   **Action (GREEN):** Run the integration test (`pytest app/tests/test_integration/`). Debug any issues found in the interaction between the API endpoint, services, Celery task execution (in eager mode), database operations, and storage. Fix bugs as needed. Make sure Tesseract is available in the environment where you run the tests (your Mac).
*   **Quality Check (REFACTOR):** Run `black .`, `isort .`, `flake8 .`, `mypy app` on any code modified during debugging.
*   **Test (REFACTOR):** Run `pytest`. All tests, including the new integration test, should pass.
*   **(Self-Verification):** Is Celery configured for eager execution in tests? Does the test use a real PDF? Does the test query the DB for `Email`, `Attachment`, *and* `AttachmentTextContent`? Does the test verify the relationships and content? Do all tests pass? Do quality checks pass?

---

**Step 12: Documentation and Heroku Preparation**

*   **Goal:** Update project documentation for the new feature and add Heroku-specific deployment considerations.
*   **TDD:** Not applicable. This is a documentation and configuration step.
*   **Action:**
    1.  Edit `README.md`:
        *   Add `celery[redis]`, `pymupdf`, `pillow`, `pytesseract` to dependencies.
        *   Add **System Dependencies** section:
            *   **macOS:** `brew install tesseract tesseract-lang redis`
            *   **Heroku:** Requires `heroku/apt` buildpack and an `Aptfile`. Note the need to install both Tesseract and PyMuPDF system dependencies.
        *   Add new environment variables:
            ```
            # Redis Configuration
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
        *   Add instructions on starting the Celery worker locally (`celery -A app.worker.celery_app worker -l info`) and mention the need for a worker dyno on Heroku.
    2.  Create/Update `Aptfile` (for Heroku):
        ```
        # Aptfile

        # OCR Dependencies
        tesseract-ocr
        libtesseract-dev
        tesseract-ocr-eng

        # PyMuPDF Dependencies (verify against your PyMuPDF version)
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
    3.  Create/Update `Procfile` (for Heroku): Add a worker process line.
        ```
        # Procfile
        web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
        release: alembic upgrade head
        worker: celery -A app.worker.celery_app worker --loglevel=info
        ```
    4.  Add clear docstrings to:
        *   `app/models/attachment_text_content.py` -> `AttachmentTextContent` class:
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
        *   `app/worker/tasks.py` -> `process_pdf_attachment` function:
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
        *   Any significantly modified methods in `AttachmentService`.
*   **Quality Check:** Manual review of documentation and Heroku files. Run `flake8` if docstring linting is enabled.
*   **Test:** Not applicable for documentation/config files directly, but the configurations will be tested during deployment.
*   **(Self-Verification):** Is README updated with all new dependencies and environment variables? Are `Aptfile` and `Procfile` created with correct content? Are PyMuPDF dependencies included? Are docstrings comprehensive and helpful? Do they follow the project's documentation style?

---

This completes the refined implementation plan, accounting for macOS development and Heroku deployment specifics. Remember to verify each step thoroughly.