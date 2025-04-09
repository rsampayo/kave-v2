"""Tests for standardized service mocking patterns.

This module provides examples and tests for the recommended mocking patterns
for external services in the application. These patterns should be followed
throughout the test suite to ensure consistency and maintainability.
"""

from typing import Any, Dict
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import Depends

from app.core.config import Settings
from app.services.storage_service import StorageService


def test_mock_factory_usage(mock_factory: Any) -> None:
    """Test the mock_factory fixture produces correctly configured mocks.

    This demonstrates the recommended way to create mocks with consistent
    configuration throughout the test suite.
    """
    # Create a mock with the factory
    mock_service = mock_factory("test_service")

    # Verify the mock was created with the expected name
    assert mock_service._extract_mock_name() == "test_service"

    # Configure mock return values
    mock_service.get_data.return_value = {"key": "value"}

    # Use the mock
    result = mock_service.get_data()

    # Verify behavior
    assert result == {"key": "value"}
    mock_service.get_data.assert_called_once()


@pytest.mark.asyncio
async def test_async_mock_factory_usage(async_mock_factory: Any) -> None:
    """Test the async_mock_factory fixture produces correctly configured async mocks."""
    # Create an async mock with the factory
    mock_service = async_mock_factory("async_service")

    # Configure async return values
    mock_service.fetch_data.return_value = {"status": "success"}

    # Use the async mock
    result = await mock_service.fetch_data()

    # Verify behavior
    assert result == {"status": "success"}
    mock_service.fetch_data.assert_awaited_once()


@pytest.mark.asyncio
async def test_mailchimp_client_mocking(mock_mailchimp_client: AsyncMock) -> None:
    """Test and demonstrate the standard pattern for mocking MailchimpClient."""
    # Configure the mock for the test case
    webhook_data = {
        "event": "inbound_email",
        "webhook_id": "test-webhook-123",
        "timestamp": "2023-01-01T12:00:00Z",
        "data": {"email": "test@example.com"},
    }

    # Set up the mock to return True for verify_webhook_signature
    mock_mailchimp_client.verify_webhook_signature.return_value = True

    # Configure parse_webhook to return the expected result
    mock_mailchimp_client.parse_webhook.return_value = webhook_data

    # Use the mock client - verify signature
    is_valid = await mock_mailchimp_client.verify_webhook_signature("valid-signature")
    assert is_valid is True

    # Use the mock client - parse webhook
    result = await mock_mailchimp_client.parse_webhook(webhook_data)

    # Verify expected behavior
    assert result == webhook_data
    mock_mailchimp_client.parse_webhook.assert_awaited_once_with(webhook_data)


@pytest.mark.asyncio
async def test_storage_service_mocking() -> None:
    """Test and demonstrate the standard pattern for mocking StorageService."""
    # Create a properly mocked StorageService
    storage_mock = AsyncMock(spec=StorageService)
    storage_mock.save_file.return_value = "s3://bucket/object_key"
    storage_mock.get_file.return_value = b"file content"

    # Use the storage mock directly first
    result1 = await storage_mock.save_file(
        file_data=b"test data", object_key="test/file.txt", content_type="text/plain"
    )

    # Verify behavior
    assert result1 == "s3://bucket/object_key"
    storage_mock.save_file.assert_awaited_once_with(
        file_data=b"test data", object_key="test/file.txt", content_type="text/plain"
    )

    # Reset the mock for the next part of the test
    storage_mock.reset_mock()

    # For patching demonstration, we need to create a test class first
    # that replaces the real class just for this test
    class TestService:
        """A test service class that replaces the real one for testing."""

        async def save_file(
            self, file_data: bytes, object_key: str, content_type: str
        ) -> str:
            return "real-implementation"

        async def get_file(self, object_key: str) -> bytes:
            return b"real-file-content"

    # Now patch the module-level import of StorageService
    # to use our test class instead
    test_path = "app.tests.test_unit.test_services.test_service_mocking.StorageService"
    with patch(test_path, TestService):
        # Create a real instance of our test class
        real_service = StorageService()

        # Patch the instance method directly
        with patch.object(
            real_service, "get_file", return_value=b"file content"
        ) as mock_get_file:
            # Call the mocked method
            file_data = await real_service.get_file(object_key="test/file.txt")

            # Verify the mocked behavior
            assert file_data == b"file content"
            mock_get_file.assert_awaited_once_with(object_key="test/file.txt")


@pytest.mark.asyncio
async def test_settings_mocking() -> None:
    """Test and demonstrate the standard pattern for mocking settings."""
    # Create a test settings object
    test_settings = Settings(
        PROJECT_NAME="Test Project",
        DATABASE_URL="sqlite+aiosqlite:///:memory:",
        SECRET_KEY="test-secret-key",
        MAILCHIMP_API_KEY="test-api-key",
        MAILCHIMP_WEBHOOK_SECRET="test-webhook-secret",
    )

    # Patch the settings object directly
    with patch("app.core.config.settings", test_settings):
        # Verify we get our patched settings
        from app.core.config import settings as imported_settings

        assert imported_settings.PROJECT_NAME == "Test Project"
        assert imported_settings.DATABASE_URL == "sqlite+aiosqlite:///:memory:"

        # This demonstrates how to use patched settings with FastAPI dependency
        def get_settings() -> Settings:
            return imported_settings

        def test_endpoint(settings: Settings = Depends(get_settings)) -> Dict[str, str]:
            return {"project": settings.PROJECT_NAME}

        # Create endpoint settings argument by calling the function directly
        result = test_endpoint(settings=get_settings())
        assert result == {"project": "Test Project"}
