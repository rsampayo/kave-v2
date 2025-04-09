# Kave Project Testing Strategy

This document outlines the testing strategy for the Kave project, providing guidance on writing, organizing, and executing tests. The goal is to maintain a comprehensive, maintainable, and effective test suite that ensures the reliability and quality of the codebase.

## Test Types and Organization

The test suite is organized into different categories, each serving a specific purpose:

### 1. Unit Tests (`app/tests/test_unit/`)

Unit tests focus on testing individual components in isolation.

- **Purpose**: Verify the behavior of specific functions, classes, or methods in isolation.
- **Scope**: Test a single unit of code with all dependencies mocked.
- **Naming Convention**: `test_unit/test_<module_type>/<test_module_name>.py` (e.g., `test_unit/test_services/test_email_service.py`)
- **Best Practices**:
  - Use extensive mocking to isolate the unit under test
  - Test each function/method's behavior in isolation
  - Test edge cases and error conditions
  - Fast execution (typically <10ms per test)
  - Use the provided mock_factory and async_mock_factory fixtures for consistent mocking

### 2. Integration Tests (`app/tests/test_integration/`)

Integration tests verify the interaction between multiple components.

- **Purpose**: Test that multiple components work together correctly.
- **Scope**: Test the integration of multiple components, such as API endpoints with their services and the database.
- **Naming Convention**: `test_integration/test_<feature_name>.py` (e.g., `test_integration/test_webhook.py`)
- **Best Practices**:
  - Use the test database for persisting and retrieving data
  - Limit mocking to external services
  - Test the complete request-response cycle
  - Verify that data flows correctly between components

### 3. End-to-End Tests (`app/tests/test_e2e/`)

End-to-end tests verify the entire application workflow.

- **Purpose**: Test complete user workflows through the entire application.
- **Scope**: Test the application as a whole, from the API to the database and back.
- **Naming Convention**: `test_e2e/test_<workflow_name>.py` (e.g., `test_e2e/test_webhook_flow.py`)
- **Best Practices**:
  - Use the application's public API
  - Minimize mocking, only mock external services when necessary
  - Test realistic user scenarios
  - Be selective about E2E tests to avoid slow test suite

## Test Database Strategy

The test suite provides multiple database options to support different testing needs:

### 1. Shared File-Based Database

- **Configuration**: Defined in `TestDatabaseConfig.TEST_DB_URL`
- **Purpose**: Persistent test database for integration and E2E tests that require data to persist across test functions
- **Usage**: Default for most tests via the `db_session` fixture
- **Lifecycle**:
  - Created once at the beginning of the test session
  - Tables dropped and recreated for each test session
  - Each test gets its own session with automatic rollback

### 2. Isolated In-Memory Database

- **Configuration**: Defined in `TestDatabaseConfig.MEMORY_DB_URL`
- **Purpose**: Completely isolated database for tests that require full isolation
- **Usage**: Available via the `isolated_db` fixture
- **Lifecycle**:
  - Created fresh for each test that uses it
  - Disposed of after the test completes

## Mocking Strategy

Consistent mocking is crucial for maintainable tests. The project provides standardized mocking patterns:

### 1. Mock Factories

- **`mock_factory`**: Creates standard MagicMock instances
- **`async_mock_factory`**: Creates standard AsyncMock instances
- **Usage**: `mock_service = mock_factory("service_name")`

### 2. Service-Specific Mocks

- **`mock_mailchimp_client`**: Pre-configured mock for MailchimpClient
- **Usage Pattern**: See `test_service_mocking.py` for examples of mocking each service type

### 3. Dependency Mocking

For testing FastAPI dependencies:

```python
# Mock a dependency
with patch("app.api.deps.get_db", return_value=mock_db):
    # Test code that uses the dependency
```

## Fixtures

The project provides several fixtures in `conftest.py` to support testing:

### Database Fixtures

- **`setup_db`**: Session-scoped fixture to initialize the test database
- **`db_session`**: Function-scoped fixture providing a fresh database session
- **`isolated_db`**: Function-scoped fixture providing an isolated in-memory database

### API Testing Fixtures

- **`app`**: Creates a test FastAPI application
- **`client`**: Provides a TestClient for synchronous endpoint testing
- **`async_client`**: Provides an AsyncClient for asynchronous endpoint testing

### Service Mocking Fixtures

- **`mock_mailchimp_client`**: Provides a mocked MailchimpClient
- **`mock_factory`**: Factory function for creating consistent MagicMock objects
- **`async_mock_factory`**: Factory function for creating consistent AsyncMock objects

## Test-Driven Development (TDD)

Follow the Red-Green-Refactor cycle as outlined in the development rules:

1. **RED**: Write a failing test first
2. **GREEN**: Write the minimum amount of code to make the test pass
3. **REFACTOR**: Improve the code while keeping the tests passing

## Coverage Requirements

- Aim for >90% code coverage
- Run `pytest --cov=app --cov-report=term-missing` to check coverage
- Pay attention to missing lines and add tests for them

## Testing External Dependencies

For any code that interacts with external services:

1. Always use mocks in unit tests
2. In integration tests, consider using test doubles or local implementations
3. Document the mocking pattern in `test_service_mocking.py`

## Migration Testing

Database migrations should be tested to ensure they perform correctly:

1. Create unit tests for migration scripts that mock the database session
2. Verify that migrations handle edge cases and errors gracefully

## Test Naming and Structure

- Use descriptive test names that explain what's being tested
- Follow the `test_<action>_<scenario>_<expected_result>` pattern
- Group related tests in classes when appropriate
- Document edge cases and complex test setups 