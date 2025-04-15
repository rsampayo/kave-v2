# API Refactoring Plan

This document outlines a step-by-step plan to refactor the API structure of the Kave application. Each step is designed to be a tiny, testable increment that maintains compatibility while gradually improving the codebase architecture.

## Principles

- Each step should be extremely small and focused (change 1-3 files maximum)
- After EVERY change: 
  - Run the full pytest suite: `pytest -xvs`
  - Run all code quality tools: 
    - Linting: `flake8`, `pylint`
    - Type checking: `mypy`
    - Code formatting: `black`, `isort`
  - Fix ANY issues found before proceeding to the next step
- Never make multiple types of changes in a single step
- Maintain backward compatibility throughout
- Improve documentation and type annotations
- Make the code more maintainable and AI-friendly

## Verification Process After Each Step

After completing each step below, always perform these verification steps:

1. Run the full test suite:
   ```bash
   pytest -xvs
   ```

2. Run all code quality tools:
   ```bash
   flake8 app/
   pylint app/
   mypy app/
   black --check app/
   isort --check app/
   ```

3. Fix any issues identified by tests or code quality tools

4. Only proceed to the next step when all tests pass and code quality checks succeed

## Phase 1: Dependency Management Refactoring

### Step 1.1: Create Dependency Directory Structure

1. Create `app/api/deps/` directory
2. Create empty `app/api/deps/__init__.py` file
3. Complete verification process (run all tests and code quality tools, fix any issues)

### Step 1.2: Create Database Dependencies Module

1. Create `app/api/deps/database.py` file
2. Copy `get_db` function from `app/db/session.py` to `app/api/deps/database.py`
3. Add appropriate imports and docstrings
4. Complete verification process (run all tests and code quality tools, fix any issues)

### Step 1.3: Update Database Dependencies Exports

1. Update `app/api/deps/__init__.py` to import and re-export `get_db`
2. Complete verification process (run all tests and code quality tools, fix any issues)

### Step 1.4: Update First Import Reference

1. Update ONE file that imports directly from `app/db/session.py` to use the new location
2. Complete verification process (run all tests and code quality tools, fix any issues)

### Step 1.5: Update Remaining Import References

1. Update one file at a time that imports `get_db` to use the new location
2. Complete verification process after updating each file
3. Continue until all files are updated

### Step 1.6: Create Storage Dependencies

1. Create `app/api/deps/storage.py`
2. Implement `get_storage_service` dependency
3. Complete verification process (run all tests and code quality tools, fix any issues)

### Step 1.7: Update Storage Dependency Exports

1. Update `app/api/deps/__init__.py` to import and re-export `get_storage_service`
2. Complete verification process (run all tests and code quality tools, fix any issues)

### Step 1.8: Update Storage Import References

1. Update one file at a time that imports `get_storage_service`
2. Complete verification process after updating each file

### Step 1.9: Create Email Dependencies

1. Create `app/api/deps/email.py`
2. Implement `get_webhook_client` dependency
3. Complete verification process (run all tests and code quality tools, fix any issues)

### Step 1.10: Update Email Client Exports

1. Update `app/api/deps/__init__.py` to import and re-export `get_webhook_client`
2. Complete verification process (run all tests and code quality tools, fix any issues)

### Step 1.11: Update Email Client Import References

1. Update one file at a time that imports `get_webhook_client`
2. Complete verification process after updating each file

### Step 1.12: Implement Email Service Dependency

1. Update `app/api/deps/email.py` to add `get_email_service` dependency
2. Update `app/api/deps/__init__.py` to export this dependency
3. Complete verification process (run all tests and code quality tools, fix any issues)

### Step 1.13: Update Email Service Import References

1. Update one file at a time that imports `get_email_service`
2. Complete verification process after updating each file

### Step 1.14: Add Type Annotations to Database Dependencies

1. Improve type annotations in `app/api/deps/database.py`
2. Add usage examples in docstrings
3. Complete verification process (run all tests and code quality tools, fix any issues)

### Step 1.15: Add Type Annotations to Storage Dependencies

1. Improve type annotations in `app/api/deps/storage.py`
2. Add usage examples in docstrings
3. Complete verification process (run all tests and code quality tools, fix any issues)

### Step 1.16: Add Type Annotations to Email Dependencies

1. Improve type annotations in `app/api/deps/email.py`
2. Add usage examples in docstrings
3. Complete verification process (run all tests and code quality tools, fix any issues)

### Step 1.17: Add Dependency Exports

1. Add `__all__` exports in each module for better IDE support
2. Complete verification process (run all tests and code quality tools, fix any issues)

### Step 1.18: Create Auth Dependencies Placeholder

1. Create `app/api/deps/auth.py` with placeholders for future auth
2. Add basic exports to `app/api/deps/__init__.py`
3. Complete verification process (run all tests and code quality tools, fix any issues)

## Phase 2: API Endpoint Restructuring

### Step 2.1: Create Router Base Directory

1. Create `app/api/routers/` directory
2. Create empty `app/api/routers/__init__.py` file
3. Complete verification process (run all tests and code quality tools, fix any issues)

### Step 2.2: Create V1 Router Directory

1. Create `app/api/routers/v1/` directory
2. Create empty `app/api/routers/v1/__init__.py` file
3. Complete verification process (run all tests and code quality tools, fix any issues)

### Step 2.3: Create Empty Attachments Router

1. Create `app/api/routers/v1/attachments.py` with an empty router
2. Complete verification process (run all tests and code quality tools, fix any issues)

### Step 2.4: Create Empty Webhooks Router

1. Create `app/api/routers/v1/webhooks.py` with an empty router
2. Complete verification process (run all tests and code quality tools, fix any issues)

### Step 2.5: Register Empty V1 Router

1. Update `app/api/routers/v1/__init__.py` to create and export a combined router
2. Complete verification process (run all tests and code quality tools, fix any issues)

### Step 2.6: Register V1 Router in Main Routers

1. Update `app/api/routers/__init__.py` to import and export the v1 router
2. Complete verification process (run all tests and code quality tools, fix any issues)

### Step 2.7: Copy Attachment Endpoint

1. Copy the attachment endpoint code from `app/api/endpoints/attachments.py` to `app/api/routers/v1/attachments.py`
2. Update imports to use new dependency locations
3. Complete verification process (run all tests and code quality tools, fix any issues)

### Step 2.8: Register Attachments Router in V1

1. Update `app/api/routers/v1/__init__.py` to include the attachment router
2. Complete verification process (run all tests and code quality tools, fix any issues)

### Step 2.9: Temporarily Register Both Attachments Routers

1. Update `app/main.py` to use both the old and new attachment endpoints (on different paths)
2. Complete verification process (run all tests and code quality tools, fix any issues)

### Step 2.10: Add Redirection from Old Attachment Endpoint

1. Update `app/api/endpoints/attachments.py` to redirect to the new endpoint
2. Add deprecation notice in the docstring
3. Complete verification process (run all tests and code quality tools, fix any issues)

### Step 2.11: Create Webhooks Router Implementation

1. Update `app/api/routers/v1/webhooks.py` to import the webhook module's router
2. Complete verification process (run all tests and code quality tools, fix any issues)

### Step 2.12: Register Webhooks Router in V1

1. Update `app/api/routers/v1/__init__.py` to include the webhook router
2. Complete verification process (run all tests and code quality tools, fix any issues)

### Step 2.13: Temporarily Register Both Webhook Routers

1. Update `app/main.py` to use both the old and new webhook endpoints (on different paths)
2. Complete verification process (run all tests and code quality tools, fix any issues)

### Step 2.14: Add Redirection from Old Webhook Endpoint

1. Update `app/api/endpoints/email_webhooks.py` to redirect to the new endpoint
2. Add deprecation notice in the docstring
3. Complete verification process (run all tests and code quality tools, fix any issues)

## Phase 3: Request/Response Standardization

### Step 3.1: Create Schema Structure

1. Create `app/schemas/` directory if not exists
2. Ensure `app/schemas/__init__.py` exists
3. Complete verification process (run all tests and code quality tools, fix any issues)

### Step 3.2: Create Attachment Schema Module

1. Create `app/schemas/attachment.py` file
2. Complete verification process (run all tests and code quality tools, fix any issues)

### Step 3.3: Implement Attachment Request Schema

1. Add one request schema to `app/schemas/attachment.py`
2. Complete verification process (run all tests and code quality tools, fix any issues)

### Step 3.4: Implement Attachment Response Schema

1. Add one response schema to `app/schemas/attachment.py`
2. Complete verification process (run all tests and code quality tools, fix any issues)

### Step 3.5: Update Attachment Schema Exports

1. Update `app/schemas/__init__.py` to export attachment schemas
2. Complete verification process (run all tests and code quality tools, fix any issues)

### Step 3.6: Create Webhook Schema Module

1. Create `app/schemas/webhook.py` file
2. Complete verification process (run all tests and code quality tools, fix any issues)

### Step 3.7: Implement Webhook Request Schema

1. Add one request schema to `app/schemas/webhook.py`
2. Complete verification process (run all tests and code quality tools, fix any issues)

### Step 3.8: Implement Webhook Response Schema

1. Add one response schema to `app/schemas/webhook.py`
2. Complete verification process (run all tests and code quality tools, fix any issues)

### Step 3.9: Update Webhook Schema Exports

1. Update `app/schemas/__init__.py` to export webhook schemas
2. Complete verification process (run all tests and code quality tools, fix any issues)

### Step 3.10: Create Error Response Module

1. Create `app/schemas/errors.py`
2. Implement basic error response schema
3. Complete verification process (run all tests and code quality tools, fix any issues)

### Step 3.11: Update Error Schema Exports

1. Update `app/schemas/__init__.py` to export error schemas
2. Complete verification process (run all tests and code quality tools, fix any issues)

### Step 3.12: Create Utils Directory

1. Create `app/api/utils/` directory
2. Create empty `app/api/utils/__init__.py`
3. Complete verification process (run all tests and code quality tools, fix any issues)

### Step 3.13: Create Error Handlers Module

1. Create `app/api/utils/error_handlers.py`
2. Implement basic error handling utility
3. Complete verification process (run all tests and code quality tools, fix any issues)

### Step 3.14: Update One Endpoint to Use Error Handler

1. Update one endpoint to use the new error handling utility
2. Complete verification process (run all tests and code quality tools, fix any issues)

### Step 3.15: Update Additional Endpoints One at a Time

1. Update one endpoint at a time to use standard error responses
2. Complete verification process after each endpoint update

### Step 3.16: Create Standard Response Module

1. Create `app/schemas/responses.py`
2. Implement basic response envelope
3. Complete verification process (run all tests and code quality tools, fix any issues)

### Step 3.17: Update Response Schema Exports

1. Update `app/schemas/__init__.py` to export response schemas
2. Complete verification process (run all tests and code quality tools, fix any issues)

### Step 3.18: Update One Endpoint to Use Response Envelope

1. Update one endpoint to use the new response envelope
2. Complete verification process (run all tests and code quality tools, fix any issues)

### Step 3.19: Update Additional Endpoints One at a Time

1. Update one endpoint at a time to use the standard response format
2. Complete verification process after each endpoint update

### Step 3.20: Add Pagination Support to Response Schema

1. Update `app/schemas/responses.py` to add pagination fields
2. Complete verification process (run all tests and code quality tools, fix any issues)

## Phase 4: Middleware and Cross-Cutting Concerns

### Step 4.1: Create Middleware Directory

1. Create `app/api/middleware/` directory
2. Create empty `app/api/middleware/__init__.py`
3. Complete verification process (run all tests and code quality tools, fix any issues)

### Step 4.2: Create CORS Middleware Module

1. Create `app/api/middleware/cors.py`
2. Complete verification process (run all tests and code quality tools, fix any issues)

### Step 4.3: Implement CORS Configuration Function

1. Move CORS configuration from `main.py` to `cors.py`
2. Implement a function to configure CORS
3. Complete verification process (run all tests and code quality tools, fix any issues)

### Step 4.4: Update Main to Use CORS Module

1. Update `main.py` to use the new CORS configuration function
2. Complete verification process (run all tests and code quality tools, fix any issues)

### Step 4.5: Create Logging Middleware Module

1. Create `app/api/middleware/logging.py`
2. Complete verification process (run all tests and code quality tools, fix any issues)

### Step 4.6: Implement Basic Request Logging

1. Implement minimal request logging middleware
2. Complete verification process (run all tests and code quality tools, fix any issues)

### Step 4.7: Register Request Logging Middleware

1. Update `app/api/middleware/__init__.py` to export the logging middleware
2. Update `main.py` to use the logging middleware
3. Complete verification process (run all tests and code quality tools, fix any issues)

### Step 4.8: Create Error Handler Middleware Module

1. Create `app/api/middleware/error_handler.py`
2. Complete verification process (run all tests and code quality tools, fix any issues)

### Step 4.9: Implement Basic Exception Handler

1. Implement a global exception handler in the middleware
2. Complete verification process (run all tests and code quality tools, fix any issues)

### Step 4.10: Register Exception Handler

1. Update `app/api/middleware/__init__.py` to export the exception handler
2. Update `main.py` to use the exception handler
3. Complete verification process (run all tests and code quality tools, fix any issues)

### Step 4.11: Update Request Logging with Correlation ID

1. Update logging middleware to add request correlation ID
2. Complete verification process (run all tests and code quality tools, fix any issues)

### Step 4.12: Improve Log Formatting

1. Update logging middleware to format logs better
2. Complete verification process (run all tests and code quality tools, fix any issues)

## Phase 5: Documentation and Testing

### Step 5.1: Update One Endpoint Documentation

1. Update documentation for one endpoint
2. Add examples
3. Complete verification process (run all tests and code quality tools, fix any issues)

### Step 5.2: Update Additional Endpoint Documentation

1. Update one endpoint's documentation at a time
2. Complete verification process after each update

### Step 5.3: Add Schema Examples

1. Add examples to one schema at a time
2. Complete verification process after each update

### Step 5.4: Add API Tags

1. Add descriptive tags to one group of endpoints
2. Complete verification process (run all tests and code quality tools, fix any issues)

### Step 5.5: Create One New Test

1. Add a test for one new middleware component
2. Complete verification process (run all tests and code quality tools, fix any issues)

### Step 5.6: Create Additional Tests

1. Add one test at a time for new components
2. Complete verification process after adding each test

### Step 5.7: Update Existing Tests

1. Update one existing test to use new structure
2. Complete verification process (run all tests and code quality tools, fix any issues)

### Step 5.8: Create Integration Test

1. Add one integration test for complete API flow
2. Complete verification process (run all tests and code quality tools, fix any issues)

### Step 5.9: Create Basic Performance Test

1. Implement a simple performance test
2. Run the test to establish baseline performance
3. Complete verification process (run all tests and code quality tools, fix any issues)

### Step 5.10: Document Performance Baselines

1. Document performance test results
2. Complete verification process (run all tests and code quality tools, fix any issues)

## Phase 6: Cleanup and Finalization

### Step 6.1: Remove One Deprecated Component

1. Remove one temporary redirect
2. Update corresponding documentation
3. Complete verification process (run all tests and code quality tools, fix any issues)

### Step 6.2: Remove Additional Deprecated Components

1. Remove one deprecated component at a time
2. Complete verification process after each removal

### Step 6.3: Run Code Quality Tools

1. Run comprehensive linting: `flake8 --max-complexity=10 app/`
2. Fix any issues
3. Complete verification process (run all tests and code quality tools, fix any issues)

### Step 6.4: Run Type Checking

1. Run type checking with strict settings: `mypy --strict app/`
2. Fix any issues
3. Complete verification process (run all tests and code quality tools, fix any issues)

### Step 6.5: Update README

1. Update main README file
2. Complete verification process (run all tests and code quality tools, fix any issues)

### Step 6.6: Update Development Documentation

1. Update developer documentation
2. Complete verification process (run all tests and code quality tools, fix any issues)

### Step 6.7: Create Migration Guide

1. Create migration guide for API users
2. Complete verification process (run all tests and code quality tools, fix any issues)

### Step 6.8: Final Testing

1. Run comprehensive test suite with coverage: `pytest -xvs --cov=app --cov-report=term-missing`
2. Fix any issues
3. Run all code quality tools with strict settings
4. Verify all documentation is accurate

## Conclusion

This refactoring plan breaks down the work into extremely small, manageable steps that can be completed over 3-4 weeks. Each tiny change is immediately tested to ensure nothing breaks, with comprehensive test and code quality verification after every step. This approach minimizes risk while steadily improving the codebase structure. The result will be a well-structured, maintainable API that follows modern best practices and is AI-friendly for future development. 