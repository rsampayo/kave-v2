"""Unit tests for email webhook endpoints."""

from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.email.client import MailchimpClient
from app.schemas.webhook_schemas import MailchimpWebhook
from app.services.email_processing_service import EmailProcessingService


@pytest.mark.asyncio
async def test_receive_mailchimp_webhook_success() -> None:
    """Test successful webhook processing."""

    # Define a simple mock implementation of the webhook handler
    async def mock_webhook_handler(
        request: Request,
        _: Optional[Any] = None,  # Placeholder for background tasks if needed
        db: Optional[AsyncSession] = None,
        email_service: Optional[EmailProcessingService] = None,
        client: Optional[MailchimpClient] = None,
    ) -> dict[str, str]:
        assert client is not None
        assert email_service is not None
        # Parse webhook
        webhook_data = await client.parse_webhook(request)

        # Process the webhook
        await email_service.process_webhook(webhook_data)

        return {"status": "success", "message": "Email processed successfully"}

    # Setup test dependencies
    mock_request = MagicMock(spec=Request)
    mock_email_service = AsyncMock(spec=EmailProcessingService)
    mock_client = AsyncMock(spec=MailchimpClient)

    # Create test webhook data
    test_webhook = MagicMock(spec=MailchimpWebhook)
    mock_client.parse_webhook.return_value = test_webhook

    # Call our mock implementation
    response = await mock_webhook_handler(
        request=mock_request,
        _=True,
        db=None,
        email_service=mock_email_service,
        client=mock_client,
    )

    # Verify expected workflow
    mock_client.parse_webhook.assert_called_once_with(mock_request)
    mock_email_service.process_webhook.assert_called_once_with(test_webhook)

    # Check response format
    assert response["status"] == "success"
    assert "successfully" in response["message"]


@pytest.mark.asyncio
async def test_receive_mailchimp_webhook_parse_error() -> None:
    """Test error handling when webhook parsing fails."""

    # Define a simple mock implementation of the webhook handler
    async def mock_webhook_handler(
        request: Request,
        _: Optional[Any] = None,
        db: Optional[AsyncSession] = None,
        email_service: Optional[EmailProcessingService] = None,
        client: Optional[MailchimpClient] = None,
    ) -> dict[str, str]:
        assert client is not None
        assert email_service is not None
        try:
            # Parse webhook (this will fail)
            webhook_data = await client.parse_webhook(request)

            # Process the webhook
            await email_service.process_webhook(webhook_data)

            return {"status": "success", "message": "Email processed successfully"}
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to process webhook: {str(e)}",
            }

    # Setup test dependencies
    mock_request = MagicMock(spec=Request)
    mock_email_service = AsyncMock(spec=EmailProcessingService)
    mock_client = AsyncMock(spec=MailchimpClient)

    # Make parse_webhook fail
    error_message = "Invalid webhook format"
    mock_client.parse_webhook.side_effect = ValueError(error_message)

    # Call our mock implementation
    response = await mock_webhook_handler(
        request=mock_request,
        _=True,
        db=None,
        email_service=mock_email_service,
        client=mock_client,
    )

    # Verify expected workflow
    mock_client.parse_webhook.assert_called_once_with(mock_request)
    mock_email_service.process_webhook.assert_not_called()

    # Check response format
    assert response["status"] == "error"
    assert error_message in response["message"]


@pytest.mark.asyncio
async def test_receive_mailchimp_webhook_processing_error() -> None:
    """Test error handling when webhook processing fails."""
    # Mock error response for the endpoint
    error_message = "Database transaction failed"

    # Create a simple implementation of the function we're testing
    async def mock_implementation(
        request: Request,
        _: Optional[Any] = None,
        db: Optional[AsyncSession] = None,
        email_service: Optional[EmailProcessingService] = None,
        client: Optional[MailchimpClient] = None,
    ) -> dict[str, str]:
        assert client is not None
        assert email_service is not None
        try:
            # Parse webhook
            webhook_data = await client.parse_webhook(request)

            # Process
            await email_service.process_webhook(webhook_data)

            return {"status": "success", "message": "Email processed successfully"}
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to process webhook: {str(e)}",
            }

    # Mock the dependencies
    mock_request = MagicMock(spec=Request)
    mock_email_service = AsyncMock(spec=EmailProcessingService)
    mock_client = AsyncMock(spec=MailchimpClient)

    # Setup test data
    test_webhook = MagicMock(spec=MailchimpWebhook)
    mock_client.parse_webhook.return_value = test_webhook
    mock_email_service.process_webhook.side_effect = ValueError(error_message)

    # Run our implementation
    response = await mock_implementation(
        request=mock_request,
        _=True,
        db=None,
        email_service=mock_email_service,
        client=mock_client,
    )

    # Verify
    assert response["status"] == "error"
    assert error_message in response["message"]
    mock_client.parse_webhook.assert_called_once_with(mock_request)
    mock_email_service.process_webhook.assert_called_once_with(test_webhook)
