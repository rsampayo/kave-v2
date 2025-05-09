"""Integration tests for the webhooks API endpoints."""

import json
from unittest.mock import patch

import httpx
import pytest
from fastapi import status
from pytest_mock import MockerFixture
from sqlalchemy.ext.asyncio import AsyncSession

# Path constant for patching
EMAIL_SERVICE_PATH = "app.services.email_service.EmailService"

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
    # Mock the organization identification to avoid DB errors
    mock_org = mocker.MagicMock()
    mock_org.name = "Test Organization"
    mock_org.id = 1

    mocker.patch(
        "app.integrations.email.client.WebhookClient.identify_organization_by_signature",
        return_value=(mock_org, True),
    )

    # Mock the parse_webhook method
    mocker.patch(
        "app.integrations.email.client.WebhookClient.parse_webhook",
        return_value=WEBHOOK_PAYLOAD,
    )

    # Create a mock email object
    mock_email = mocker.MagicMock()
    mock_email.id = "test-email-id-123"

    # Mock the email service's process_webhook method
    with patch(f"{EMAIL_SERVICE_PATH}.process_webhook") as mock_process:
        # Configure the mock to return our mock email
        mock_process.return_value = mock_email

        # Send the webhook request
        response = await async_client.post(
            "/v1/webhooks/mandrill",
            headers={"X-Mailchimp-Signature": "test-signature"},
            content=json.dumps(WEBHOOK_PAYLOAD),
        )

    # Verify the response
    assert response.status_code == status.HTTP_202_ACCEPTED
    response_json = response.json()
    assert response_json["status"] == "success"
    assert "Email processed successfully" in response_json["message"]

    # Verify that the process_webhook method was called
    mock_process.assert_called_once()


@pytest.mark.asyncio
async def test_webhook_endpoint_empty_array(async_client: httpx.AsyncClient) -> None:
    """Test webhook endpoint with empty array - simulating Mandrill webhook testing."""
    # Send the webhook request with an empty array as Mandrill would for testing
    response = await async_client.post(
        "/v1/webhooks/mandrill",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Mandrill-Webhook/1.0",
        },
        data={"mandrill_events": "[]"},
    )

    # Verify the response is 200 OK and properly acknowledges the empty array
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "status": "success",
        "message": "Empty events list acknowledged",
    }


@pytest.mark.asyncio
async def test_webhook_signature_validation(
    async_client: httpx.AsyncClient, mocker: MockerFixture, db_session: AsyncSession
) -> None:
    """Test webhook with signature validation."""
    # Mock the organization
    from app.models.organization import Organization

    mock_org = Organization(
        id=1,
        name="Test Organization",
        webhook_email="recipient@example.com",
        mandrill_webhook_secret="test-secret",
        is_active=True,
    )

    # Mock the identify_organization_by_signature method
    mocker.patch(
        "app.integrations.email.client.WebhookClient.identify_organization_by_signature",
        return_value=(mock_org, True),  # Return the org and True for verified
    )

    # Mock the email service's process_webhook method
    with patch(f"{EMAIL_SERVICE_PATH}.process_webhook") as mock_process:
        # Configure the mock to return a specific email ID
        mock_process.return_value = "test-email-id-123"

        # Send the webhook request with signature header
        response = await async_client.post(
            "/v1/webhooks/mandrill",
            headers={"X-Mailchimp-Signature": "valid-signature"},
            content=json.dumps(WEBHOOK_PAYLOAD),
        )

    # Verify the response
    assert response.status_code == status.HTTP_202_ACCEPTED
    assert response.json() == {
        "status": "success",
        "message": "Email processed successfully",
    }

    # Verify that the process_webhook method was called with the organization
    mock_process.assert_called_once()
    args, kwargs = mock_process.call_args
    assert "organization" in kwargs
    assert kwargs["organization"] == mock_org


@pytest.mark.asyncio
async def test_webhook_signature_validation_rejection(
    async_client: httpx.AsyncClient, mocker: MockerFixture, db_session: AsyncSession
) -> None:
    """Test webhook signature validation with rejection of invalid signatures."""
    # Mock the organization lookup to return None and False (not verified)
    mocker.patch(
        "app.integrations.email.client.WebhookClient.identify_organization_by_signature",
        return_value=(None, False),
    )

    # Mock the settings object with all required properties
    class MockSettings:
        API_ENV = "testing"
        MAILCHIMP_WEBHOOK_BASE_URL_PRODUCTION = "https://api.example.com"
        MAILCHIMP_WEBHOOK_BASE_URL_TESTING = "https://test.example.com/webhook"
        MAILCHIMP_REJECT_UNVERIFIED_PRODUCTION = True
        MAILCHIMP_REJECT_UNVERIFIED_TESTING = True

        @property
        def should_reject_unverified(self):
            return True

        @property
        def get_webhook_url(self):
            return "https://test.example.com/webhook"

    mock_settings = MockSettings()

    # Patch the settings in the router module
    mocker.patch(
        "app.api.v1.endpoints.webhooks.mandrill.router.settings", mock_settings
    )

    # Send the webhook request with an invalid signature
    response = await async_client.post(
        "/v1/webhooks/mandrill",
        headers={"X-Mailchimp-Signature": "invalid-signature"},
        content=json.dumps(WEBHOOK_PAYLOAD),
    )

    # Verify that we got the rejection response
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json() == {
        "status": "error",
        "message": "Invalid webhook signature",
    }
