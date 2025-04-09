# Kave Project Refactoring Plan (AI Implementation Guide)

## 1. Introduction

This document outlines a refactoring plan for the Kave project. The goal is to align the codebase with industry best practices and strictly adhere to the project's `development_rules.mdc`. This plan is intended to be implemented by an AI assistant, following the specified workflow and quality standards meticulously.

**Core Principles (from `development_rules.mdc`):**
*   **TDD First:** All changes MUST follow the Red-Green-Refactor cycle. Write failing tests *before* code changes.
*   **Iterative Quality:** Run `black .`, `isort .`, `flake8 .`, and `mypy app` frequently during the Refactor step and fix ALL issues according to project standards (`pyproject.toml`, `setup.cfg`).
*   **Configuration Adherence:** Strictly follow settings for Black (88 lines), Flake8 (complexity 12, specific selects/ignores), and MyPy (strict typing).
*   **Dependency Management:** Use `pip-compile` via `requirements/*.in` files.
*   **Commit Granularity:** Make small, logical commits.

## 2. Configuration Refinements

### 2.1. ✅ Verify/Remove Redundant Mypy Configurations (`mypy.ini`, `.mypy.ini`, `pyproject.toml`)
    *   **COMPLETED:** Successfully consolidated all mypy configurations into `pyproject.toml`:
        *   Merged settings from `.mypy.ini` and `mypy.ini` into the `[tool.mypy]` section in `pyproject.toml`
        *   Adjusted configurations to maintain compatibility (disabled `warn_unreachable`, added error codes to `disable_error_code`)
        *   Added plugin configurations for SQLAlchemy and Pydantic
        *   Added module-specific overrides for API, tests, and config files
        *   Removed redundant `.mypy.ini` and `mypy.ini` files
        *   Verified type checking passes and all tests run successfully

### 2.2. Environment-Aware CORS Configuration (`app/main.py`, `app/core/config.py`)
    *   **RED:** Write a test (e.g., using `TestClient`) that asserts the `access-control-allow-origin` header is set correctly based on different environment variable settings (e.g., one for `dev`, one for `prod`). This might require mocking `settings`.
    *   **GREEN:**
        *   Add a `CORS_ALLOWED_ORIGINS` setting to `app/core/config.py:Settings`. Use `list[str]` or `str` (if comma-separated). Provide a default (e.g., `[]` or `""`) and load from the environment.
        *   Update `app/main.py:create_application` to use `settings.CORS_ALLOWED_ORIGINS` for the `allow_origins` parameter in `CORSMiddleware`. Handle potential string-to-list conversion if needed.
        *   Update `.env` and `.env.example` with `CORS_ALLOWED_ORIGINS`. Set a restrictive default for production (e.g., your frontend domain) and potentially `["*"]` or specific local origins for development in `.env`.
    *   **REFACTOR:** Clean up the implementation. Run quality checks and tests.

## 3. Type Hinting Improvements (`pyproject.toml`, relevant `.py` files)

### 3.1. ✅ Address Mypy `ignore_missing_imports` (`pyproject.toml`, `app/integrations/email/models.py`, `app/db/session_management.py`)
    *   **COMPLETED:** Successfully removed unnecessary `ignore_missing_imports` overrides:
        *   Temporarily removed the `ignore_missing_imports = true` override for both modules
        *   Discovered that no type errors occurred without the override
        *   Found that SQLAlchemy 2.0 provides its own mypy plugin that conflicts with type stubs
        *   Removed both the email models and session management overrides
        *   Removed the redundant SQLAlchemy override as well
        *   Verified all tests and type checking pass without these overrides
        *   Updated the mypy configuration with explanatory comments

### 3.2. ✅ Improve Test Function Typing (`app/tests/**/*.py`)
    *   **COMPLETED:** Evaluated the test function typing and found it was already in good shape:
        *   Temporarily made the mypy configuration stricter for test files (`disallow_untyped_defs = true`) 
        *   Checked multiple test files and found they already had appropriate type annotations
        *   All test functions include return type annotations (`-> None`)
        *   Helper functions and fixtures have appropriate return type annotations
        *   Verified that mypy passes with no errors, even with stricter settings
        *   Current test override settings (`disallow_untyped_defs = false`) are appropriate to maintain flexibility

## 4. Linter Rule Adherence (`setup.cfg`/`pyproject.toml`, relevant `.py` files)

### 4.1. Review `B008` Ignore (`pyproject.toml`/`setup.cfg`)
    *   **Action:** Manually review code sections where `B008` might be relevant (function calls in argument defaults). Confirm it's primarily due to FastAPI `Depends()` or Pydantic `Field(default_factory=...)`. If mutable defaults (like `arg: list = []`) are found, refactor them using factories or `None` defaults (`arg: list | None = None; if arg is None: arg = []`). No specific Red/Green needed unless actual mutable defaults are found and require refactoring (which would then follow TDD).

### 4.2. Fix `E501` Ignore (`app/tests/test_unit/test_db/test_session.py`, `pyproject.toml`/`setup.cfg`)
    *   **RED:** Write a test (or modify an existing one) that indirectly relies on the logic within the long line(s) in `test_session.py`. Temporarily remove the `per-file-ignores` for `E501` in the Flake8 config. Run `flake8 .` and confirm it fails for `test_session.py`.
    *   **GREEN:** Refactor the specific line(s) in `test_session.py` that exceed 88 characters. Break them down logically using standard Python line continuation (parentheses, backslashes if necessary) while maintaining readability.
    *   **REFACTOR:** Remove the `per-file-ignores` entry for `test_session.py:E501` from the Flake8 configuration. Run quality checks and tests.

## 5. Database Session Management (`app/db/session.py`, `app/dependencies/`, `app/api/**/*.py`)

*   **Action:** Review `app/db/session.py` and any files in `app/dependencies/` (if it exists).
    *   Confirm a dependency function (e.g., `get_db`) exists that:
        *   Creates a `SessionLocal` instance.
        *   Uses a `try...finally` block to ensure `session.close()` is always called.
        *   Uses `yield session`.
    *   Confirm API route functions use `db: Session = Depends(get_db)`.
    *   Ensure `engine` and `SessionLocal` are initialized appropriately (likely top-level in `session.py`).
    *   If deviations are found, apply TDD: Write a test ensuring correct session handling/closure, make the code changes to use the standard dependency pattern, refactor.

## 6. API Endpoint Refinements (`app/api/**/*.py`, `app/services/**/*.py`, `app/schemas/**/*.py`)

*   **Action (Iterative TDD per endpoint/feature):**
    *   **Lean Endpoints:** For each API route function:
        *   **RED:** Write/refine integration tests asserting the endpoint's response (status code, body) for various inputs, focusing on the *contract*. Write unit tests for the underlying service logic.
        *   **GREEN:** Ensure the route function primarily handles: Request validation (via Pydantic models), calling the appropriate service layer function(s), and formatting the response (using response models). Move complex logic, database interactions, or calls to external systems into the service layer.
        *   **REFACTOR:** Improve clarity, inject service dependencies if needed. Run quality checks and tests.
    *   **Standardization:** Review endpoints for consistent use of:
        *   HTTP status codes (e.g., 200, 201, 204, 400, 404, 422).
        *   `response_model` definitions.
        *   Error handling (raising `HTTPException` for client errors, using custom handlers for server/domain errors - see Section 8).
        *   Apply TDD for any necessary refactoring.
    *   **OpenAPI Docs:** Enhance documentation:
        *   Add/improve function docstrings (summary, description).
        *   Use Pydantic `Field(..., description="...", example="...")` in schemas.
        *   Use `tags`, `summary`, `description` parameters in router methods (`@router.get(...)`).

## 7. Service Layer Structure (`app/services/**/*.py`)

*   **Action (Iterative TDD per service):**
    *   **Single Responsibility:** Review each service class/module. Ensure it focuses on a specific domain area. Refactor large services into smaller, more focused ones if necessary.
    *   **Testability:** Ensure services are easily unit-testable. Dependencies (like DB sessions, other services, external API clients) should be passed into methods or initialized via `__init__` (Dependency Injection). Use mocking (`pytest-mock`) extensively in unit tests.
    *   **Business Logic:** Confirm that the core business logic resides here, not in API endpoints or database models.
    *   Apply TDD for all refactoring.

## 8. Error Handling Strategy (`app/main.py`, `app/core/exceptions.py`, `app/api/**/*.py`)

*   **Action (Apply TDD):**
    *   **RED:** Write tests that trigger specific domain errors or expected exceptions (e.g., item not found, validation error from an external service). Assert that the correct HTTP status code and a standardized JSON error response body are returned.
    *   **GREEN:**
        *   Create `app/core/exceptions.py` if it doesn't exist. Define custom exception classes inheriting from `Exception` (e.g., `ItemNotFoundError`, `ExternalServiceError`).
        *   In `app/main.py` (or a dedicated `app/error_handlers.py`), define exception handlers using `@app.exception_handler(...)` for your custom exceptions and potentially for generic `Exception`. These handlers should log the full error and return a `JSONResponse` with a standardized error schema (e.g., `{"detail": "Error message"}`).
        *   Modify service/API code to raise custom exceptions where appropriate, instead of generic `Exception` or overly broad `HTTPException`. Catch specific external library exceptions in services and re-raise as custom exceptions if needed.
    *   **REFACTOR:** Clean up handler implementation, ensure consistent error responses. Run quality checks and tests.
    *   **(Optional) Structured Logging:** Configure logging (in `app/main.py` or `app/core/logging.py`) to output JSON logs for easier parsing (e.g., using `python-json-logger`).

## 9. Security Enhancements

*   **Action (Review and Apply TDD where applicable):**
    *   **Authentication/Authorization:** Review how endpoints are protected. If using JWT or OAuth2, ensure implementation is robust (correct algorithms, key management via `settings`, token validation, scope checks). Add/refine tests for protected endpoints (unauthorized and authorized access).
    *   **Rate Limiting:** Consider adding rate limiting (e.g., using `slowapi`) to public or sensitive endpoints. Implement with tests.
    *   **Security Headers:** Add security headers (e.g., `X-Content-Type-Options`, `X-Frame-Options`, `Content-Security-Policy`) via middleware. Test their presence.
    *   **Input Validation:** Continue leveraging Pydantic, but double-check validation logic, especially for complex or nested models.

## 10. Testing Strategy Refinements (`app/tests/**/*.py`, `conftest.py`)

*   **Action (Review and Apply TDD):**
    *   **Balance:** Review the test suite (`pytest --collect-only -q`). Ensure a good mix of unit tests (fast, isolated, mocking external dependencies) and integration tests (testing interactions, e.g., API endpoint -> service -> DB).
    *   **Test Database:** Confirm integration tests use a separate, ephemeral test database. Ensure proper setup/teardown (e.g., using fixtures, potentially `alembic upgrade head` before tests and teardown after).
    *   **Mocking:** Standardize mocking of external services (MailChimp, S3). Use `pytest-mock` (`mocker` fixture) consistently. Create reusable mock fixtures in `conftest.py` if applicable.
    *   **Fixtures (`conftest.py`):** Review fixtures for appropriate scope (`session`, `function`, `module`, `class`). Make them reusable and focused. Ensure proper type hinting for fixtures.

## 11. Final Checks

*   Run the full test suite (`pytest`).
*   Run all quality checks (`black .`, `isort .`, `flake8 .`, `mypy app`). Fix any remaining issues.
*   Check test coverage (`pytest --cov=app`). Ensure it meets the project target (>90%). Add tests for any significant gaps introduced during refactoring.

**Reminder:** Each step involving code changes MUST follow the Red-Green-Refactor cycle outlined in `development_rules.mdc`. 