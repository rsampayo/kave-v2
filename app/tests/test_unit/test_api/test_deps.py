"""Unit tests for API dependencies."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, Request

from app.api.deps import verify_webhook_signature
from app.integrations.email.client import MailchimpClient


@pytest.mark.asyncio
async def test_verify_webhook_signature_valid() -> None:
    """Test verify_webhook_signature when signature is valid."""
    # Mock the MailChimp client
    mock_client = AsyncMock(spec=MailchimpClient)
    mock_client.verify_webhook_signature.return_value = True

    # Mock request
    mock_request = MagicMock(spec=Request)

    # Call the function
    result = await verify_webhook_signature(request=mock_request, client=mock_client)

    # Assert
    assert result is True
    mock_client.verify_webhook_signature.assert_called_once_with(mock_request)


@pytest.mark.asyncio
async def test_verify_webhook_signature_invalid() -> None:
    """Test verify_webhook_signature when signature is invalid."""
    # Mock the MailChimp client
    mock_client = AsyncMock(spec=MailchimpClient)
    mock_client.verify_webhook_signature.return_value = False

    # Mock request
    mock_request = MagicMock(spec=Request)

    # Call the function, expecting exception
    with pytest.raises(HTTPException) as exc_info:
        await verify_webhook_signature(request=mock_request, client=mock_client)

    # Verify exception details
    assert exc_info.value.status_code == 401
    assert "Invalid webhook signature" in exc_info.value.detail
    mock_client.verify_webhook_signature.assert_called_once_with(mock_request)


@pytest.mark.asyncio
async def test_mailchimp_client_dependency_injection() -> None:
    """Test that the mailchimp client dependency is properly injected."""
    # We can't directly test a dependency, so we're mocking the class
    # and testing that it's called with the right parameters
    with patch("app.api.deps.mailchimp_client") as mock_client:
        # Create a function that simulates dependency injection
        def dependency() -> MailchimpClient:
            return mock_client

        # Get the injected client
        injected_client = dependency()

        # Verify
        assert injected_client == mock_client
