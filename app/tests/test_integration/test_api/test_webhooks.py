"""Integration tests for the webhooks API endpoints."""

import json
from unittest.mock import patch

import httpx
import pytest
from fastapi import status
from pytest_mock import MockerFixture
from sqlalchemy.ext.asyncio import AsyncSession

# Path constant for patching
EMAIL_SERVICE_PATH = "app.services.email_processing_service.EmailProcessingService"

# Test data for the webhook
WEBHOOK_PAYLOAD = {
    "webhook_id": "test-id-123",
    "event": "inbound_email",
    "timestamp": "2023-01-01T12:00:00Z",
    "data": {
        "message_id": "test@example.com",
        "from_email": "sender@example.com",
        "subject": "Test Subject",
        "body_plain": "Test Email Content",
        "body_html": "<p>HTML Content</p>",
        "to_email": "recipient@example.com",
        "headers": {},
        "attachments": [],
    },
}

# Test webhook with attachment data
WEBHOOK_PAYLOAD_WITH_ATTACHMENTS = {
    "webhook_id": "test-id-456",
    "event": "inbound_email",
    "timestamp": "2023-01-01T12:00:00Z",
    "data": {
        "message_id": "test@example.com",
        "from_email": "sender@example.com",
        "subject": "Test with Attachments",
        "body_plain": "Email with attachments",
        "body_html": "<p>HTML Content with attachments</p>",
        "to_email": "recipient@example.com",
        "headers": {},
        "attachments": [
            {
                "name": "test.pdf",
                "type": "application/pdf",
                "content": "base64contentstringhere",
            }
        ],
    },
}


@pytest.mark.asyncio
async def test_webhook_endpoint_successful(
    async_client: httpx.AsyncClient, mocker: MockerFixture, db_session: AsyncSession
) -> None:
    """Test successful webhook processing endpoint."""
    # Mock the mailchimp client's verify_webhook_signature method
    mocker.patch(
        "app.integrations.email.client.mailchimp_client.verify_webhook_signature",
        return_value=True,
    )

    # Mock the email service's process_webhook method
    with patch(f"{EMAIL_SERVICE_PATH}.process_webhook") as mock_process:
        # Configure the mock to return a specific email ID
        mock_process.return_value = "test-email-id-123"

        # Send the webhook request
        response = await async_client.post(
            "/webhooks/mailchimp",
            headers={"X-Mailchimp-Signature": "test-signature"},
            content=json.dumps(WEBHOOK_PAYLOAD),
        )

    # Verify the response
    assert response.status_code == status.HTTP_202_ACCEPTED
    assert response.json() == {
        "status": "success",
        "message": "Email processed successfully",
    }

    # Verify that the process_webhook method was called
    mock_process.assert_called_once()


@pytest.mark.asyncio
async def test_webhook_endpoint_processing_error(
    async_client: httpx.AsyncClient, mocker: MockerFixture, db_session: AsyncSession
) -> None:
    """Test webhook endpoint with a processing error."""
    # Mock the mailchimp client's verify_webhook_signature method
    mocker.patch(
        "app.integrations.email.client.mailchimp_client.verify_webhook_signature",
        return_value=True,
    )

    # Mock the parse_webhook method to return valid data
    mocker.patch(
        "app.integrations.email.client.mailchimp_client.parse_webhook",
        return_value=WEBHOOK_PAYLOAD,
    )

    # Mock the email service to raise an exception during processing
    with patch(f"{EMAIL_SERVICE_PATH}.process_webhook") as mock_process:
        # Configure the mock to raise an exception
        mock_process.side_effect = Exception("Test processing error")

        # Send the webhook request
        response = await async_client.post(
            "/webhooks/mailchimp",
            headers={"X-Mailchimp-Signature": "test-signature"},
            content=json.dumps(WEBHOOK_PAYLOAD),
        )

    # Verify the response
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    response_json = response.json()
    assert response_json["status"] == "error"
    assert (
        "processing" in response_json["message"].lower()
        or "Test processing error" in response_json["message"]
    )
