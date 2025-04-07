# Refactoring Plan for FastAPI Project

## Goal

This document outlines the plan to refactor the FastAPI project codebase. The objectives are to improve project structure, enhance maintainability, increase security, ensure better adherence to defined development standards (TDD, code quality), and improve performance where applicable.

## Phase 1: Project Structure & Cleanup (Foundation)

This phase focuses on organizing the project layout and removing clutter for better clarity.

**Step 1.1: Clean Root Directory**

*   **Action:** Move test-related files (`test_webhook.py`, `test_webhook_with_attachment.py`) from the root directory into the appropriate sub-directory within `app/tests/` (e.g., `app/tests/test_integration/` or `app/tests/test_e2e/`).
*   **Action:** Move mock data files (`mock_webhook.json`, `mock_webhook_with_attachment.json`) from the root directory into `app/tests/test_data/`.
*   **Action:** Evaluate experimental/example files (`simplified_app.py`, `test_app.py`, `test_db_connection.py`) in the root. If still useful as examples, move them to a new `examples/` directory. If obsolete, delete them.
*   **Action:** Evaluate `setup.py`. If its functionality is fully covered by `pyproject.toml` (likely), remove it. If it contains essential custom build logic, document why it's needed.
*   **Rationale:** Creates a cleaner, more standard project root, making it easier to navigate and understand the project structure.

**Step 1.2: Verify `.gitignore`**

*   **Action:** Review the `.gitignore` file. Ensure it includes standard Python/FastAPI exclusions (`*.pyc`, `__pycache__/`, `venv*/`, `.venv/`, `.mypy_cache/`, `htmlcov/`, `.pytest_cache/`, `.coverage*`) and project-specific files like `dev.db`, `error.log`, `.env`.
*   **Rationale:** Prevents generated files, environment secrets, and local development artifacts from being committed to version control.

**Step 1.3: Remove Empty Directories**

*   **Action:** Delete the empty directories `app/agents/` and `app/tools/`.
*   **Rationale:** Removes unused placeholders, simplifying the `app/` directory structure.

## Phase 2: Configuration & Environment Management (Consistency & Security)

This phase focuses on standardizing configuration and ensuring environment-specific settings are handled correctly.

**Step 2.1: Configure CORS Origins via Settings**

*   **Action:** In `app/core/config.py`, define a setting for allowed CORS origins (e.g., `BACKEND_CORS_ORIGINS: list[str] = ["http://localhost:3000"]`) using Pydantic `Settings`, potentially loading from environment variables.
*   **Action:** In `app/main.py`, update the `CORSMiddleware` to use this setting: `allow_origins=settings.BACKEND_CORS_ORIGINS`.
*   **Rationale:** Improves security by restricting allowed origins based on environment, removing the insecure `"*"` wildcard for production.

**Step 2.2: Configure `ATTACHMENTS_DIR` via Settings**

*   **Action:** In `app/core/config.py`, define a setting for the base attachments directory (e.g., `ATTACHMENTS_BASE_DIR: Path = Path("data/attachments")`).
*   **Action:** In `app/services/email_processing_service.py`, remove the hardcoded `ATTACHMENTS_DIR` constant. Import `settings` and use `settings.ATTACHMENTS_BASE_DIR` when constructing file paths.
*   **Rationale:** Centralizes configuration, allows environment-specific paths, and improves code maintainability.

**Step 2.3: Manage Database Schema Creation**

*   **Action:** In `app/main.py`'s `lifespan` function, either remove the `await conn.run_sync(Base.metadata.create_all)` call *or* make it conditional (e.g., `if settings.ENVIRONMENT == "development": ...`).
*   **Action:** Ensure the deployment process (e.g., `Procfile` release phase, CI/CD script) reliably executes `alembic upgrade head` *before* the application server starts.
*   **Rationale:** Enforces the use of Alembic for all schema management, preventing potential conflicts between `create_all` and migrations, especially in production.

## Phase 3: Core Logic Refinement (Attachments Handling)

This phase addresses specific implementation details in the email processing service related to attachments.

**Step 3.1: Refactor Attachment Path Storage**

*   **Action:** Modify the `Attachment` model (`app/models/email_data.py`) to store a *relative* path or unique identifier instead of the full, absolute path in the `file_path` column.
*   **Action:** Update `app/services/email_processing_service.py` (`process_attachments` function) to save only this relative path/identifier to the database model.
*   **Action:** Implement a helper function or property (potentially in the `Attachment` model itself, or a utility module) that combines the `settings.ATTACHMENTS_BASE_DIR` with the stored relative path/identifier to generate the full path when needed for file access.
*   **Rationale:** Decouples the database schema from the specific deployment filesystem structure, making the application more portable and easier to adapt to different storage solutions (e.g., cloud storage).

**Step 3.2: Review Attachment Content Storage in Database**

*   **Action:** Determine if storing the binary `content` of attachments directly in the `Attachment` database table is necessary, given that it's also being saved to the filesystem.
*   **Action:** If filesystem storage is sufficient, remove the `attachment.content = content` assignment in `process_attachments` and consider making the `content` column in the `Attachment` model nullable or removing it entirely (requires an Alembic migration).
*   **Rationale:** Avoids database bloat and potential performance issues associated with storing large binary objects in database rows if they aren't frequently accessed directly from the DB.

**Step 3.3: Implement Async File I/O for Attachments**

*   **Action:** Add `aiofiles` to `requirements/requirements.in` and regenerate `requirements.txt` (`pip-compile requirements.in`).
*   **Action:** In `app/services/email_processing_service.py` (`process_attachments`), replace the synchronous file writing block (`with open(...)`) with the asynchronous equivalent: `async with aiofiles.open(full_file_path, "wb") as afp: await afp.write(decoded_content)`. Ensure you have the `decoded_content` and the `full_file_path` (constructed using the base dir and relative path).
*   **Rationale:** Prevents blocking the FastAPI asynchronous event loop during file I/O, improving application responsiveness and performance under load.

## Phase 4: Code Quality & Typing

This phase focuses on enhancing static analysis adherence.

**Step 4.1: Review and Tighten MyPy Overrides**

*   **Action:** Examine the `[[tool.mypy.overrides]]` sections in `pyproject.toml`, particularly for `tests.*` and `api.endpoints.*`.
*   **Action:** Attempt to add missing type hints within the affected modules (`.py` files in `app/tests/` and `app/api/endpoints/`).
*   **Action:** Incrementally try to remove or make the MyPy override rules stricter (e.g., re-enable `disallow_untyped_defs = true`) for these sections, fixing any revealed type errors.
*   **Rationale:** Improves code robustness and maintainability by leveraging static typing more fully across the codebase, aligning with the project's defined quality standards.

## Conclusion

Executing this refactoring plan will result in a cleaner, more organized, robust, secure, and maintainable codebase. It addresses structural issues, improves configuration management, refines core logic related to attachments, and enhances adherence to static typing rules. Each phase builds upon the previous one, ensuring a methodical approach to improving the project's quality. 