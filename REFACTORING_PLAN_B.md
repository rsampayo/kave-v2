# Refactoring Plan for FastAPI Project

## 1. Introduction

This document outlines a step-by-step plan to refactor the FastAPI project codebase based on a detailed analysis. The objectives are to align the codebase with industry best practices and the specific guidelines outlined in `development_rules.mdc`, focusing on:

*   Improving dependency management and reproducibility.
*   Enhancing type safety and code quality enforcement.
*   Increasing security (specifically CORS configuration).
*   Improving code structure and separation of concerns.
*   Simplifying database session management.
*   Removing ambiguity and potential technical debt (deprecated fields, naming collisions).

**Core Principle:** Each step should follow the **Red-Green-Refactor** cycle implicitly where applicable (though most are direct refactors). Crucially, after each logical step or group of steps, all code quality checks (**Black, isort, Flake8, MyPy**) and tests (**pytest**) MUST pass as per `development_rules.mdc`.

## 2. Prerequisites

*   Ensure the current codebase is in a clean Git state (no uncommitted changes).
*   Verify that all existing tests pass (`pytest`).
*   Verify that all code quality checks pass (`black . --check`, `isort . --check`, `flake8 .`, `mypy app`).
*   Create a new Git branch for this refactoring effort (e.g., `refactor/codebase-improvements`).

## 3. Refactoring Steps

---

### Step 3.1: Implement `pip-compile` Workflow

*   **Action:** Transition dependency management from manually edited `.txt` files to `pip-compile` generated files based on `.in` files.
*   **Files Involved:**
    *   `requirements/base.in` (Create)
    *   `requirements/dev.in` (Create)
    *   `requirements/integrations.in` (Create)
    *   `requirements/base.txt` (Will be overwritten)
    *   `requirements/dev.txt` (Will be overwritten)
    *   `requirements/integrations.txt` (Will be overwritten)
*   **Reason:** Enforces `development_rules.mdc` regarding dependency management, ensures reproducible builds, and properly pins transitive dependencies.
*   **Procedure:**
    1.  **Create `requirements/base.in`:** List only direct *production* dependencies found in the original `base.txt`.
        ```ini
        # requirements/base.in
        fastapi>=0.109.0,<0.110.0
        uvicorn>=0.28.0,<0.29.0
        pydantic>=2.6.0,<3.0.0
        pydantic-settings>=2.1.0,<3.0.0
        sqlalchemy>=2.0.0,<3.0.0
        alembic>=1.15.0,<1.16.0
        python-multipart>=0.0.9,<0.0.10
        email-validator>=2.1.0,<3.0.0
        python-dotenv>=1.0.0,<2.0.0
        asyncpg>=0.29.0,<0.30.0
        aiosqlite>=0.19.0,<0.20.0
        httpx>=0.27.0,<0.28.0
        greenlet>=3.1.0,<4.0.0 # Often needed by sqlalchemy async
        boto3>=1.34.0,<1.35.0
        aiofiles>=24.1.0,<25.0.0
        # Add any other direct prod dependencies here
        ```
    2.  **Create `requirements/integrations.in`:** Include `base.in` and direct integration dependencies.
        ```ini
        # requirements/integrations.in
        -r base.in
        python-dateutil>=2.8.2,<3.0.0
        mailchimp-marketing>=3.0.0,<4.0.0
        mailchimp-transactional>=1.0.0,<2.0.0
        aiohttp>=3.9.0,<4.0.0 # Example if mailchimp clients need it
        ```
    3.  **Create `requirements/dev.in`:** Include `integrations.in` and direct development/testing dependencies. Add `boto3-stubs` here (for Step 3.8).
        ```ini
        # requirements/dev.in
        -r integrations.in
        pytest>=8.0.0,<9.0.0
        pytest-cov>=4.1.0,<5.0.0
        pytest-asyncio>=0.23.0,<0.24.0
        black>=25.1.0,<26.0.0
        isort>=5.13.0,<6.0.0
        flake8>=7.0.0,<8.0.0
        flake8-bugbear>=24.2.0,<25.0.0
        flake8-docstrings>=1.7.0,<2.0.0
        flake8-comprehensions>=3.14.0,<4.0.0
        autoflake>=2.3.0,<3.0.0
        mypy>=1.8.0,<2.0.0
        types-python-dateutil>=2.8.0,<3.0.0
        pip-tools>=7.3.0,<8.0.0
        # Type stubs
        types-aiofiles>=24.1.0.20250326,<25.0.0
        boto3-stubs[s3]>=1.34.0 # Add this line
        # Add any other direct dev dependencies
        ```
    4.  **Generate `.txt` files:**
        ```bash
        pip-compile requirements/base.in -o requirements/base.txt --upgrade
        pip-compile requirements/integrations.in -o requirements/integrations.txt --upgrade
        pip-compile requirements/dev.in -o requirements/dev.txt --upgrade
        ```
    5.  **Install updated dependencies:** `pip install -r requirements/dev.txt`
    6.  **Commit changes:** Add *all* `.in` and `.txt` files to the commit.
*   **Verification:** Ensure the application still runs and tests pass (`pytest`).

---

### Step 3.2: Update MyPy Configuration

*   **Action:** Add `disallow_untyped_calls = true` and remove redundant `check_untyped_defs = true` in `pyproject.toml`.
*   **File Involved:** `pyproject.toml`
*   **Reason:** Fully align MyPy configuration with the stricter requirements defined in `development_rules.mdc`.
*   **Procedure:** Modify the `[tool.mypy]` section:
    ```diff
     [tool.mypy]
     python_version = "3.11"
     disallow_untyped_defs = true
     disallow_incomplete_defs = true
    -check_untyped_defs = true
    +disallow_untyped_calls = true # Add this line
     disallow_untyped_decorators = true
     no_implicit_optional = true
     strict_optional = true

    ```
*   **Verification:** Run `mypy app`. Fix any *new* errors reported due to the stricter checks (likely involving calls to untyped functions, potentially in tests or involving libraries without stubs). Run `pytest`.

---

### Step 3.3: Enhance CORS Security

*   **Action:** Modify CORS middleware configuration to restrict allowed origins in non-development environments.
*   **File Involved:** `app/main.py`
*   **Reason:** Critical security enhancement to prevent CSRF attacks in production/staging environments, aligning with security best practices.
*   **Procedure:** Update the `create_application` function:
    ```python
    # app/main.py
    # ... other imports
    from app.core.config import settings # Ensure settings is imported

    # ... lifespan function ...

    def create_application() -> FastAPI:
        app = FastAPI(
            title=settings.PROJECT_NAME,
            description="AI agent platform that processes emails from MailChimp",
            version="0.1.0",
            lifespan=lifespan,
        )

        # Configure CORS based on environment
        origins = []
        if settings.API_ENV == "development":
            logger.warning("Allowing all origins in development environment")
            # Allow all for local development ease
            origins = ["*"]
        else:
            # Add specific production/staging frontend origins here
            # Example: origins = ["https://your-app.com", "https://staging.your-app.com"]
            # Ensure this list is populated with actual trusted origins
            # If no frontend, or only accessed via specific backend, adjust accordingly
            origins = settings.ALLOWED_HOSTS or [] # Assuming ALLOWED_HOSTS is defined in settings, else define explicitly
            if not origins:
                 logger.warning("No production origins configured for CORS")


        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins, # Use the dynamic list
            allow_credentials=True,
            # Restrict methods and headers if possible for tighter security
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"], # Example: Be specific
            allow_headers=["*"], # Example: ["Content-Type", "Authorization"]
        )

        # Include API routers
        app.include_router(email_webhooks.router)
        app.include_router(attachments.router, prefix="/attachments", tags=["attachments"])

        return app

    app = create_application()
    ```
    *Note: You might need to add `ALLOWED_HOSTS: List[str] = []` to your `app/core/config.py` settings model, loading it from an environment variable.*
*   **Verification:** Run `pytest`. Manually test API access from allowed/disallowed origins if possible, especially in a staging environment.

---

### Step 3.4: Refactor Attachment Endpoint Logic

*   **Action:** Move database query and storage fallback logic for fetching attachments from the API endpoint to the `StorageService`.
*   **Files Involved:**
    *   `app/services/storage_service.py`
    *   `app/api/endpoints/attachments.py`
    *   `app/models/email_data.py` (Potentially needed for type hints)
*   **Reason:** Improves separation of concerns, adheres to the service layer pattern, makes the endpoint cleaner.
*   **Procedure:**
    1.  **Add new method to `StorageService` (`app/services/storage_service.py`):**
        ```python
        # Add imports at the top if not present
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession
        from app.models.email_data import Attachment # Add this import
        from fastapi import HTTPException # Add this import

        class StorageService:
            # ... (existing __init__, save_file, get_file methods) ...

            async def get_attachment_data_with_fallback(
                self, attachment_id: int, db: AsyncSession
            ) -> tuple[bytes, str, str]:
                """Get attachment data, trying storage_uri then DB content.

                Args:
                    attachment_id: The ID of the attachment to retrieve.
                    db: The database session for querying attachment metadata.

                Returns:
                    A tuple containing (file_data, content_type, filename).

                Raises:
                    HTTPException: With status 404 if the attachment or its content
                                   cannot be found.
                """
                # Query for the attachment metadata
                result = await db.execute(
                    select(Attachment).where(Attachment.id == attachment_id)
                )
                attachment = result.scalar_one_or_none()

                if not attachment:
                    logger.warning(f"Attachment with ID {attachment_id} not found in DB.")
                    raise HTTPException(status_code=404, detail="Attachment not found")

                file_data: bytes | None = None
                filename: str = attachment.filename or "download"
                content_type: str = attachment.content_type or "application/octet-stream"

                # 1. Try fetching from storage_uri using existing get_file
                if attachment.storage_uri:
                    logger.info(f"Attempting to fetch attachment {attachment_id} from storage URI: {attachment.storage_uri}")
                    file_data = await self.get_file(attachment.storage_uri)
                    if not file_data:
                         logger.warning(f"Attachment {attachment_id} found in DB but failed to fetch from storage_uri: {attachment.storage_uri}")


                # 2. Fallback: Try fetching from deprecated DB content field
                #    Remove this block once the 'content' column is dropped.
                if not file_data and attachment.content:
                    logger.warning(f"Attachment {attachment_id} fetched from deprecated 'content' DB field.")
                    file_data = attachment.content

                # Check if content was successfully retrieved
                if file_data is None:
                     logger.error(f"Content for attachment {attachment_id} could not be retrieved from storage_uri or DB field.")
                     raise HTTPException(
                         status_code=404, detail="Attachment content not available"
                     )

                return file_data, content_type, filename

        # ... (existing get_storage_service) ...
        ```
    2.  **Update `get_attachment` endpoint (`app/api/endpoints/attachments.py`):**
        ```python
        # Remove unused imports: from sqlalchemy import select; from app.models.email_data import Attachment
        from fastapi import APIRouter, Depends, HTTPException, Response # Keep Response
        from sqlalchemy.ext.asyncio import AsyncSession # Keep AsyncSession if needed by deps
        from app.db.session import get_db # Keep get_db
        from app.services.storage_service import StorageService, get_storage_service # Keep storage service

        router = APIRouter()

        @router.get(
            "/{attachment_id}",
            summary="Download attachment",
            description=(
                "Download an email attachment by its ID. "
                "Retrieves attachment from cloud storage or database."
            ),
            # Keep response_model=None or adjust if needed, raw Response is returned
        )
        async def get_attachment(
            attachment_id: int,
            db: AsyncSession = Depends(get_db), # Keep db if needed by storage service method
            storage: StorageService = Depends(get_storage_service),
        ) -> Response:
            """Get an attachment file by ID by calling the storage service.

            Args:
                attachment_id: The ID of the attachment
                db: Database session (passed to storage service)
                storage: Storage service

            Returns:
                Response: The attachment file content

            Raises:
                HTTPException: Forwarded from storage service if not found/unavailable
            """
            try:
                # Delegate fetching and fallback logic to the storage service
                file_data, content_type, filename = await storage.get_attachment_data_with_fallback(
                    attachment_id, db
                )

                # Return the file as a response
                return Response(
                    content=file_data,
                    media_type=content_type,
                    headers={
                        # Use repr() for filename to handle potential special characters
                        "Content-Disposition": f"attachment; filename={filename!r}"
                    },
                )
            except HTTPException as e:
                 # Re-raise HTTPException if thrown by the service (e.g., 404)
                 raise e
            except Exception as e:
                 # Catch unexpected errors during service call
                 logger.error(f"Unexpected error retrieving attachment {attachment_id}: {e}")
                 raise HTTPException(status_code=500, detail="Internal server error retrieving attachment")

        ```
*   **Verification:** Run quality checks (`black`, `isort`, `flake8`, `mypy`). Run tests (`pytest`), paying attention to tests covering the attachment download endpoint.

---

### Step 3.5: Simplify DB Session Management

*   **Action:** Remove the custom `TrackedAsyncSession` subclass and use the standard `AsyncSession`.
*   **File Involved:** `app/db/session.py`
*   **Reason:** Simplifies code, removes unnecessary complexity. Standard session management is sufficient.
*   **Procedure:**
    1.  Remove the `TrackedAsyncSession` class definition.
    2.  Update `get_db` and `get_session` to use the factory directly.
    ```python
    # app/db/session.py
    from typing import Any, AsyncGenerator # Keep AsyncGenerator

    from sqlalchemy.ext.asyncio import (
        AsyncEngine,
        AsyncSession, # Keep AsyncSession
        async_sessionmaker,
        create_async_engine,
    )
    from sqlalchemy.orm import declarative_base

    from app.core.config import settings

    # ... (Base, DATABASE_URL, engine definitions remain the same) ...

    # Create session factory
    async_session_factory = async_sessionmaker(
        engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        class_=AsyncSession # Ensure class_ is explicitly AsyncSession if needed
    )

    # REMOVE the entire TrackedAsyncSession class definition

    # ... (init_db remains the same) ...

    async def get_db() -> AsyncGenerator[AsyncSession, None]:
        """Dependency provider for database sessions."""
        # Use the factory directly
        async with async_session_factory() as session:
            try:
                yield session
            except Exception:
                 await session.rollback()
                 raise
            # No explicit commit needed here as endpoints/services handle it
            finally:
                # The context manager handles closing
                 pass


    # Optional: If get_session is truly needed outside DI
    def get_session() -> AsyncSession:
        """Get a new database session (manual lifecycle management required)."""
        # Use the factory directly
        return async_session_factory()

    ```
*   **Verification:** Run quality checks. Run `pytest`. Ensure database interactions in tests and application still function correctly.

---

### Step 3.6: Rename `EmailAttachment` DTO

*   **Action:** Rename the non-ORM `EmailAttachment` class in `models/email_data.py` to avoid conflict with the Pydantic schema.
*   **Files Involved:**
    *   `app/models/email_data.py`
    *   `app/services/email_processing_service.py`
*   **Reason:** Improves code clarity and avoids potential confusion between the DTO and the Pydantic schema.
*   **Procedure:**
    1.  **Rename class in `app/models/email_data.py`:**
        ```diff
        # ... Attachment model definition ...

        -class EmailAttachment:
        +class EmailAttachmentDTO:
             """DTO for passing attachment data in API requests and tests.

             This is a non-ORM class that serves as a data transfer object for
        ```
        *(Update the `__init__` method name if necessary, though it should remain `__init__`)*
    2.  **Update usage in `app/services/email_processing_service.py`:**
        ```diff
        # Import the renamed DTO
        -from app.models.email_data import Attachment, Email, EmailAttachment
        +from app.models.email_data import Attachment, Email, EmailAttachmentDTO # Update import
        from app.schemas.webhook_schemas import EmailAttachment as SchemaEmailAttachment # Schema remains the same
        # ... other imports ...

        # Update adapter function signature and usage
        def _schema_to_model_attachment(
            schema_attachment: SchemaEmailAttachment,
        -) -> EmailAttachment:
        +) -> EmailAttachmentDTO: # Update return type hint
            """Convert schema EmailAttachment to model EmailAttachment DTO."""
        -    return EmailAttachment(
        +    return EmailAttachmentDTO( # Use renamed DTO
                name=schema_attachment.name,
                type=schema_attachment.type,
                content=schema_attachment.content or "",
                content_id=schema_attachment.content_id,
                size=schema_attachment.size,
            )

        # Update adapter function signature
        def _schema_to_model_attachments(
            schema_attachments: List[SchemaEmailAttachment],
        -) -> List[EmailAttachment]:
        +) -> List[EmailAttachmentDTO]: # Update return type hint
             """Convert list of schema attachments to model attachments DTOs."""
            return [_schema_to_model_attachment(a) for a in schema_attachments]

        class EmailProcessingService:
            # ... __init__ ...

            # Update type hint in process_attachments if it used the old name directly
             async def process_attachments(
                 self, email_id: int, attachments: List[EmailAttachmentDTO] # Update type hint
             ) -> List[Attachment]: # Return type is ORM model, remains Attachment
                 # ... implementation uses attach_data which is now EmailAttachmentDTO ...
                 result = []
                 for attach_data in attachments: # attach_data is an instance of EmailAttachmentDTO
                     # ... existing logic accessing attach_data.name, .type etc ...
        ```
*   **Verification:** Run quality checks. Run `pytest`.

---

### Step 3.7: Address Test Session Typing Ignore

*   **Action:** Investigate and attempt to resolve the `# type: ignore[call-overload]` comment associated with `TestSessionLocal` in the test configuration.
*   **File Involved:** `app/tests/conftest.py`
*   **Reason:** Improves static analysis accuracy and removes ignored type errors.
*   **Procedure:**
    1.  Examine the `TestSessionLocal = sessionmaker(...)` line.
    2.  The issue likely stems from `sessionmaker` being primarily designed for synchronous sessions, although it can be adapted for async. Ensure `class_=AsyncSession` is correctly passed.
    3.  Try explicitly providing type hints if MyPy can infer them:
        ```python
        # app/tests/conftest.py
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine # Ensure imports

        # ... test_engine definition ...

        # Create a test session factory - Explicitly type?
        TestSessionFactory = sessionmaker(
            bind=test_engine,
            class_=AsyncSession,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )

        # ... fixtures using TestSessionFactory() ...

        @pytest_asyncio.fixture
        async def db_session() -> AsyncGenerator[AsyncSession, None]:
             # Use the explicitly typed factory
             session = TestSessionFactory()
             try:
                 # ... yield, rollback, close ...
        ```
    4.  If the above doesn't resolve it, consult SQLAlchemy/MyPy documentation for the exact signature mismatch or consider if `async_sessionmaker` (used in main code) could be used here too (might require adjustments to session scope handling if tests rely on specific `sessionmaker` behavior).
    5.  If a clean fix isn't readily apparent, leave the `type: ignore` but add a comment explaining *why* it's needed.
*   **Verification:** Run `mypy app`. The goal is to remove the `type: ignore` comment *if possible* while keeping MyPy passing. Run `pytest`.

---

### Step 3.8: Add `boto3-stubs` and Verify Typing

*   **Action:** Add `boto3-stubs[s3]` as a dev dependency (done in Step 3.1) and remove `# type: ignore` comments related to `aioboto3`/`botocore`.
*   **File Involved:** `app/services/storage_service.py`
*   **Reason:** Enables proper static type checking for AWS SDK interactions.
*   **Procedure:**
    1.  Ensure `boto3-stubs[s3]` is listed in `requirements/dev.in` and installed (should be from Step 3.1).
    2.  Remove `# type: ignore` comments from `aioboto3` and `botocore.exceptions` imports and usage within `StorageService`.
        ```diff
        # app/services/storage_service.py
         import logging
         from typing import Optional

        -import aioboto3  # type: ignore
        -import aiofiles
        -from botocore.exceptions import ClientError  # type: ignore
        +import aioboto3 # Remove ignore
        +import aiofiles
        +from botocore.exceptions import ClientError # Remove ignore

         from app.core.config import settings
        ```
*   **Verification:** Run `mypy app`. Ensure MyPy passes without the ignores. Run `pytest` focusing on tests involving S3 storage if applicable.

---

### Step 3.9: Address Flake8 Ignore

*   **Action:** Review the `per-file-ignores` for `E501` (line too long) in `setup.cfg` and attempt to refactor the offending line(s).
*   **Files Involved:**
    *   `setup.cfg`
    *   `app/tests/test_unit/test_db/test_session.py` (The file with the long line)
*   **Reason:** Strives for full compliance with code quality rules (line length).
*   **Procedure:**
    1.  Open `app/tests/test_unit/test_db/test_session.py`.
    2.  Identify the line(s) exceeding 88 characters.
    3.  Attempt to refactor the line(s) by breaking them down logically (e.g., assigning intermediate variables, breaking long function calls/assertions across multiple lines within parentheses/brackets).
    4.  If successfully refactored, remove the corresponding `# noqa: E501` comment from the line itself (if present) and remove the `per-file-ignores` entry from `setup.cfg`.
    5.  If refactoring significantly harms readability or is not feasible, leave the ignore in place but ensure it's justified.
*   **Verification:** Run `flake8 .`. Ensure no `E501` errors are reported (or only the intentionally ignored one remains if refactoring wasn't possible). Run `pytest`.

---

### Step 3.10: Plan Deprecated Column Removal (Future Work)

*   **Action:** Add TODO comments or create backlog items to track the removal of deprecated database columns. **No code changes in this step.**
*   **Files Involved:** `app/models/email_data.py` (for TODO comments)
*   **Reason:** Acknowledges technical debt identified during the review and schedules its removal.
*   **Procedure:**
    1.  Add specific TODO comments near the deprecated fields:
        ```python
        # app/models/email_data.py
        class Attachment(Base):
            # ... other columns ...

            # TODO: [Refactor/RemoveDeprecated] Create Alembic migration to drop file_path column after verifying no usage.
            file_path: Mapped[Optional[str]] = mapped_column(...)
            # TODO: [Refactor/RemoveDeprecated] Create Alembic migration to drop content column after verifying no usage and fallback logic is removed from StorageService.
            content: Mapped[Optional[bytes]] = mapped_column(...)

            # ... storage_uri, email relationship ...
        ```
    2.  Optionally, create tickets/issues in your project management system referencing these TODOs.
*   **Verification:** N/A (Documentation/Planning step).

---

## 4. Post-Refactoring Checks

*   Run all code quality tools one last time:
    *   `black .`
    *   `isort .`
    *   `flake8 .`
    *   `mypy app`
*   Run all tests: `pytest`
*   Ensure test coverage meets the >90% requirement (`pytest --cov=app`). Analyze the report if needed.

## 5. Conclusion

Upon successful completion of these steps, the codebase will be more robust, maintainable, secure, and fully compliant with the defined `development_rules.mdc`. Dependency management will be standardized, type safety increased, potential security vulnerabilities addressed, and code structure improved.
