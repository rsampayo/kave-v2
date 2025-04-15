# House Cleaning Plan

## Overview
This document outlines a step-by-step plan for cleaning up the codebase according to the project's development philosophy and rules. It focuses on maintaining code quality, addressing test failures, removing unused files, and organizing the project structure without making unnecessary changes.

## Phase 1: Clean Up Temporary Files

1. Remove Python cache files:
   ```bash
   find . -name "*.pyc" -delete
   find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
   ```

2. Remove macOS system files:
   ```bash
   find . -name ".DS_Store" -delete
   ```

3. Clean up log files in the root directory:
   ```bash
   rm -f error.log server.log
   ```

4. Remove pytest/coverage artifacts:
   ```bash
   rm -rf .pytest_cache
   rm -f .coverage*
   ```

## Phase 2: Organize Root Directory Files

1. Move testing scripts to appropriate directories:
   ```bash
   mkdir -p scripts/tests
   git mv test_*.py scripts/tests/
   git mv debug_webhook.py scripts/
   git mv webhook_test.py scripts/tests/
   git mv check_s3.py scripts/
   ```

2. Organize documentation:
   ```bash
   mkdir -p docs/implementation
   git mv implement_signature*.md docs/implementation/
   git mv SIGNATURE_DEBUGGING.md docs/implementation/
   git mv api_refactoring_plan.md docs/
   git mv refactoring-plan.md docs/
   ```

3. Clean up duplicate/obsolete files:
   ```bash
   # Before deleting, verify these files are truly obsolete
   # git rm .coverage\ 2
   # git rm signature_implementation_tracker.json  # Only if no longer needed
   ```

## Phase 3: Fix Test Failures

1. Run tests to identify failures:
   ```bash
   cd app
   pytest -v tests/test_e2e/test_webhook_flow.py
   pytest -v tests/test_integration/test_api/test_webhook_integration.py
   pytest -v tests/test_integration/test_api/test_webhooks.py
   pytest -v tests/test_integration/test_webhook.py
   pytest -v tests/test_integration/test_webhook_with_attachment.py
   ```

2. Follow TDD approach for each failure:
   - Analyze test failure reason
   - Make minimal changes to fix each test
   - Run code quality tools after fixing

## Phase 4: Dependency Management

1. Update dependencies using pip-compile:
   ```bash
   pip-compile requirements.in
   pip-compile requirements-dev.in
   ```

2. Install updated dependencies:
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt  # If you have this file
   ```

3. Verify application still works:
   ```bash
   python -m app.main  # Or however you start the application
   ```

## Phase 5: Code Quality Verification

1. Run and fix mypy issues:
   ```bash
   mypy app
   ```

2. Run and fix flake8 issues:
   ```bash
   flake8 app
   ```

3. Format code with Black:
   ```bash
   black app
   ```

4. Sort imports with isort:
   ```bash
   isort app
   ```

5. Run test coverage and analyze:
   ```bash
   pytest --cov=app --cov-report=term-missing --cov-report=xml
   ```

## Phase 6: Documentation Updates

1. Review README.md for accuracy
2. Update .env.example if any new environment variables have been added
3. Verify that project documentation is up-to-date

## Phase 7: Final Verification

1. Ensure all tests pass:
   ```bash
   pytest
   ```

2. Verify the application runs without errors
3. Commit changes with a clear commit message describing what was cleaned up

## Guidelines for Implementing Changes

1. **Minimal Changes Policy**: Make only the changes outlined in this plan; do not refactor or enhance functionality unless specifically required to fix a test.

2. **Test-Driven Development**: When fixing failing tests, follow the Red-Green-Refactor cycle.

3. **Iterative Code Quality**: After each change, run the appropriate code quality tools (Black, isort, Flake8, MyPy).

4. **Organize Logically**: When moving files, ensure they are placed in directories that match their purpose.

5. **Test Before Committing**: Ensure all tests pass after implementing changes. 