# Refactoring Plan for FastAPI Project

## Goal

This document outlines the plan to refactor the FastAPI project codebase. The objectives are to improve project structure, enhance maintainability, increase security, ensure better adherence to defined development standards (TDD, code quality), and improve performance where applicable.

## Phase 1: Project Structure & Cleanup (Foundation) - **COMPLETED**

This phase focuses on organizing the project layout and removing clutter for better clarity.

**Step 1.1: Clean Root Directory** - **COMPLETED**

*   ✅ **Action:** Move test-related files (`test_webhook.py`, `test_webhook_with_attachment.py`) from the root directory into the appropriate sub-directory within `app/tests/` (e.g., `app/tests/test_integration/` or `app/tests/test_e2e/`).
    * **Completed:** April 7, 2025. Moved both test files to `app/tests/test_integration/`. Updated file paths in the tests to point to the new location of mock data files.
*   ✅ **Action:** Move mock data files (`mock_webhook.json`, `mock_webhook_with_attachment.json`) from the root directory into `app/tests/test_data/`.
    * **Completed:** April 7, 2025. Created copies of these files in `app/tests/test_data/` and removed the originals from the root directory.
*   ✅ **Action:** Evaluate experimental/example files (`simplified_app.py`, `test_app.py`, `test_db_connection.py`) in the root. If still useful as examples, move them to a new `examples/` directory. If obsolete, delete them.
    * **Completed:** April 7, 2025. Created an `examples` directory and moved `simplified_app.py` and `test_db_connection.py` there as they're useful for reference and debugging. Added a README.md file to document their usage. Deleted `test_app.py` as it was too minimal to be useful.
*   ✅ **Action:** Evaluate `setup.py`. If its functionality is fully covered by `pyproject.toml` (likely), remove it. If it contains essential custom build logic, document why it's needed.
    * **Completed:** April 7, 2025. Removed `setup.py` as its functionality was already covered by the `pyproject.toml` and the comprehensive requirements files in the `requirements/` directory.
*   **Rationale:** Creates a cleaner, more standard project root, making it easier to navigate and understand the project structure.

**Step 1.2: Verify `.gitignore`** - **COMPLETED**

*   ✅ **Action:** Review the `.gitignore` file. Ensure it includes standard Python/FastAPI exclusions (`*.pyc`, `__pycache__/`, `venv*/`, `.venv/`, `.mypy_cache/`, `htmlcov/`, `.pytest_cache/`, `.coverage*`) and project-specific files like `dev.db`, `error.log`, `.env`.
    * **Completed:** April 7, 2025. The `.gitignore` file was already quite comprehensive. Added missing patterns for `.mypy_cache/`, `.dmypy.json`, `dmypy.json`, and `.coverage.*`. Removed outdated references to mock webhook files that have been moved to the test_data directory.
*   **Rationale:** Prevents generated files, environment secrets, and local development artifacts from being committed to version control.

**Step 1.3: Remove Empty Directories** - **COMPLETED**

*   ✅ **Action:** Delete the empty directories `app/agents/` and `app/tools/`.
    * **Completed:** April 7, 2025. Verified that both directories were empty and removed them, simplifying the project structure.
*   **Rationale:** Removes unused placeholders, simplifying the `app/` directory structure.

## Phase 2: Configuration & Environment Management (Consistency & Security) - **COMPLETED**

This phase focuses on standardizing configuration and ensuring environment-specific settings are handled correctly.

**Step 2.1: Configure `ATTACHMENTS_DIR` via Settings** - **COMPLETED**

*   ✅ **Action:** In `app/core/config.py`, define a setting for the base attachments directory (e.g., `ATTACHMENTS_BASE_DIR: Path = Path("data/attachments")`).
    * **Completed:** June 14, 2024. Added the `ATTACHMENTS_BASE_DIR` setting to the Settings class in `app/core/config.py` with a default value of `Path("data/attachments")`.
*   ✅ **Action:** In `app/services/email_processing_service.py`, remove the hardcoded `ATTACHMENTS_DIR` constant. Import `settings` and use `settings.ATTACHMENTS_BASE_DIR` when constructing file paths.
    * **Completed:** June 14, 2024. Removed the hardcoded `ATTACHMENTS_DIR` constant and modified the code to use `settings.ATTACHMENTS_BASE_DIR` instead. Updated all references to use the configuration setting rather than the hardcoded constant.
*   **Rationale:** Centralizes configuration, allows environment-specific paths, and improves code maintainability.

**Step 2.2: Manage Database Schema Creation** - **COMPLETED**

*   ✅ **Action:** In `app/main.py`'s `lifespan` function, either remove the `await conn.run_sync(Base.metadata.create_all)` call *or* make it conditional (e.g., `if settings.ENVIRONMENT == "development": ...`).
    * **Completed:** June 15, 2024. Removed the `create_all` call entirely from the lifespan function and updated the docstring to indicate that schema should be managed through Alembic migrations instead.
*   ✅ **Action:** Ensure the deployment process (e.g., `Procfile` release phase, CI/CD script) reliably executes `alembic upgrade head` *before* the application server starts.
    * **Completed:** June 15, 2024. Created a Procfile with a `release: alembic upgrade head` command that will run migrations before the web process starts. Also updated the README.md with a new Database Migrations section explaining the process.
*   **Rationale:** Enforces the use of Alembic for all schema management, preventing potential conflicts between `create_all` and migrations, especially in production.

## Phase 3: Core Logic Refinement (Attachments Handling) - **COMPLETED**

This phase addresses specific implementation details in the email processing service related to attachments.

**Step 3.1: Refactor Attachment Path Storage** - **COMPLETED**

*   ✅ **Action:** Modify the `Attachment` model (`app/models/email_data.py`) to store a *relative* path or unique identifier instead of the full, absolute path in the `file_path` column.
    * **Completed:** The model now includes a new `storage_uri` field that stores a URI (either `s3://` or `file://`) instead of absolute paths.
*   ✅ **Action:** Update `app/services/email_processing_service.py` (`process_attachments` function) to save only this relative path/identifier to the database model.
    * **Completed:** The code now saves the storage URI returned by the storage service.
*   ✅ **Action:** Implement a helper function or property (potentially in the `Attachment` model itself, or a utility module) that combines the `settings.ATTACHMENTS_BASE_DIR` with the stored relative path/identifier to generate the full path when needed for file access.
    * **Completed:** June 16, 2024. The StorageService class now handles this functionality with methods that parse and construct URIs as needed.
*   **Rationale:** Decouples the database schema from the specific deployment filesystem structure, making the application more portable and easier to adapt to different storage solutions (e.g., cloud storage).

**Step 3.2: Review Attachment Content Storage in Database** - **COMPLETED**

*   ✅ **Action:** Determine if storing the binary `content` of attachments directly in the `Attachment` database table is necessary, given that it's also being saved to the filesystem.
    * **Completed:** June 16, 2024. Determined that storing content in the database is redundant since it's also stored in either the filesystem or S3.
*   ✅ **Action:** If filesystem storage is sufficient, remove the `attachment.content = content` assignment in `process_attachments` and consider making the `content` column in the `Attachment` model nullable or removing it entirely (requires an Alembic migration).
    * **Completed:** June 16, 2024. Removed the assignment and updated the model documentation to mark the field as deprecated. Created a migration script (remove_attachment_content.py) to ensure the column is nullable for backward compatibility.
*   **Rationale:** Avoids database bloat and potential performance issues associated with storing large binary objects in database rows if they aren't frequently accessed directly from the DB.

**Step 3.3: Implement Async File I/O for Attachments** - **COMPLETED**

*   ✅ **Action:** Add `aiofiles` to `requirements/requirements.in` and regenerate `requirements.txt` (`pip-compile requirements.in`).
    * **Completed:** June 16, 2024. Added aiofiles to requirements/base.txt with version constraint >=24.1.0,<25.0.0.
*   ✅ **Action:** In `app/services/email_processing_service.py` (`process_attachments`), replace the synchronous file writing block (`with open(...)`) with the asynchronous equivalent: `async with aiofiles.open(full_file_path, "wb") as afp: await afp.write(decoded_content)`. Ensure you have the `decoded_content` and the `full_file_path` (constructed using the base dir and relative path).
    * **Completed:** June 16, 2024. Updated the StorageService._save_to_filesystem and StorageService._get_from_filesystem methods to use aiofiles for async file I/O.
*   **Rationale:** Prevents blocking the FastAPI asynchronous event loop during file I/O, improving application responsiveness and performance under load.

## Phase 4: Code Quality & Typing - **COMPLETED**

This phase focuses on enhancing static analysis adherence.

**Step 4.1: Review and Tighten MyPy Overrides** - **COMPLETED**

*   ✅ **Action:** Examine the `[[tool.mypy.overrides]]` sections in `pyproject.toml`, particularly for `tests.*` and `api.endpoints.*`.
    * **Completed:** June 16, 2024. Reviewed all mypy overrides and identified unnecessary configurations.
*   ✅ **Action:** Attempt to add missing type hints within the affected modules (`.py` files in `app/tests/` and `app/api/endpoints/`).
    * **Completed:** June 16, 2024. All API endpoints had sufficient type hints. Added missing type hints to database migration files.
*   ✅ **Action:** Incrementally try to remove or make the MyPy override rules stricter (e.g., re-enable `disallow_untyped_defs = true`) for these sections, fixing any revealed type errors.
    * **Completed:** June 16, 2024. Completely removed the mypy override for the api/endpoints modules as they were unnecessary. Tightened the type checking for tests by enabling check_untyped_defs, warn_return_any, and warn_unreachable.
*   **Rationale:** Improves code robustness and maintainability by leveraging static typing more fully across the codebase, aligning with the project's defined quality standards.

## Conclusion

Executing this refactoring plan will result in a cleaner, more organized, robust, secure, and maintainable codebase. It addresses structural issues, improves configuration management, refines core logic related to attachments, and enhances adherence to static typing rules. Each phase builds upon the previous one, ensuring a methodical approach to improving the project's quality.

**Current Progress:**
- Phase 1: Project Structure & Cleanup - **COMPLETED** ✅ 
- Phase 2: Configuration & Environment Management - **COMPLETED** ✅
- Phase 3: Core Logic Refinement - **COMPLETED** ✅
- Phase 4: Code Quality & Typing - **COMPLETED** ✅

**All refactoring tasks have been completed successfully!** 