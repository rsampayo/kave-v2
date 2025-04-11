"""Unit tests for the webhook client integration."""

import base64
from datetime import datetime
from typing import Any, Dict

import pytest
from fastapi import HTTPException

from app.integrations.email.client import WebhookClient


@pytest.fixture
def webhook_client() -> WebhookClient:
    """Create a test instance of WebhookClient."""
    return WebhookClient(
        webhook_secret="test_secret", api_key="test_key-us1", server_prefix="us1"
    )


@pytest.fixture
def webhook_payload() -> Dict[str, Any]:
    """Create a test webhook payload."""
    return {
        "webhook_id": "test-webhook-123",
        "event": "inbound_email",
        "fired_at": "2023-05-01T12:00:00Z",
        "data": {
            "message_id": "test-message-id",
            "from_email": "sender@example.com",
            "from_name": "Test Sender",
            "to_email": "recipient@example.com",
            "subject": "Test Subject",
            "body_plain": "This is a test email",
            "body_html": "<p>This is a test email</p>",
            "headers": {
                "Message-ID": "<test-message-id>",
                "Date": "Mon, 1 May 2023 12:00:00 +0000",
                "From": "Test Sender <sender@example.com>",
                "To": "recipient@example.com",
                "Subject": "Test Subject",
            },
            "attachments": [],
        },
    }


@pytest.mark.asyncio
async def test_validate_webhook_data_valid(
    webhook_client: WebhookClient, webhook_payload: Dict[str, Any]
) -> None:
    """Test validating a valid webhook payload."""
    # When we validate the payload
    # This should not raise an exception
    await webhook_client._validate_webhook_data(webhook_payload)

    # Test passes if no exception is raised


@pytest.mark.asyncio
async def test_validate_webhook_data_invalid_event(
    webhook_client: WebhookClient, webhook_payload: Dict[str, Any]
) -> None:
    """Test validating a webhook with an invalid event type."""
    # Given an invalid event type
    webhook_payload["event"] = "invalid_event_type"

    # When we validate
    with pytest.raises(HTTPException) as exc_info:
        await webhook_client._validate_webhook_data(webhook_payload)

    # Then it should raise an appropriate error
    assert exc_info.value.status_code == 400
    assert "Unsupported webhook event" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_validate_webhook_data_missing_data(
    webhook_client: WebhookClient, webhook_payload: Dict[str, Any]
) -> None:
    """Test validating a webhook without a data field."""
    # Given a payload without the data field
    del webhook_payload["data"]

    # When we validate
    with pytest.raises(HTTPException) as exc_info:
        await webhook_client._validate_webhook_data(webhook_payload)

    # Then it should raise an appropriate error
    assert exc_info.value.status_code == 400
    assert "'data' field is required" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_validate_attachment_valid(webhook_client: WebhookClient) -> None:
    """Test validating a valid attachment."""
    # Given a valid attachment
    attachment = {
        "name": "test.txt",
        "type": "text/plain",
        "content": "SGVsbG8gd29ybGQ=",  # Base64 "Hello world"
    }

    # When we validate
    result = webhook_client._validate_attachment(attachment)

    # Then it should be valid
    assert result is True


@pytest.mark.asyncio
async def test_validate_attachment_invalid(webhook_client: WebhookClient) -> None:
    """Test validating an invalid attachment."""
    # Given an invalid attachment missing required fields
    attachment = {
        "content": "SGVsbG8gd29ybGQ=",  # Base64 "Hello world"
    }

    # When we validate
    result = webhook_client._validate_attachment(attachment)

    # Then it should be invalid
    assert result is False


@pytest.mark.asyncio
async def test_parse_webhook_valid(
    webhook_client: WebhookClient, webhook_payload: Dict[str, Any]
) -> None:
    """Test parsing a valid webhook payload."""
    # When we parse the webhook
    # In tests, we're using a Dict directly instead of a Request object
    result = await webhook_client.parse_webhook(webhook_payload)  # type: ignore

    # Then it should contain the expected fields
    assert result.webhook_id == webhook_payload["webhook_id"]
    assert result.event == webhook_payload["event"]
    assert isinstance(result.timestamp, datetime)
    assert result.data is not None


@pytest.mark.asyncio
async def test_parse_webhook_invalid_event(
    webhook_client: WebhookClient, webhook_payload: Dict[str, Any]
) -> None:
    """Test parsing a webhook with invalid event type."""
    # Given an invalid event type
    webhook_payload["event"] = "invalid_event"

    # When we try to parse it
    with pytest.raises(HTTPException) as exc_info:
        # In tests, we're using a Dict directly instead of a Request object
        await webhook_client.parse_webhook(webhook_payload)  # type: ignore

    # Then it should raise an error
    assert exc_info.value.status_code == 400
    assert "Unsupported webhook event" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_parse_webhook_missing_data(
    webhook_client: WebhookClient, webhook_payload: Dict[str, Any]
) -> None:
    """Test parsing a webhook with missing data."""
    # Given missing required data
    del webhook_payload["data"]

    # When we try to parse it
    with pytest.raises(HTTPException) as exc_info:
        # In tests, we're using a Dict directly instead of a Request object
        await webhook_client.parse_webhook(webhook_payload)  # type: ignore

    # Then it should raise an error
    assert exc_info.value.status_code == 400
    assert "payload" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_parse_webhook_with_attachments(
    webhook_client: WebhookClient, webhook_payload: Dict[str, Any]
) -> None:
    """Test parsing a webhook with attachments."""
    # Given a webhook with attachments
    test_content = "Test attachment content"
    test_content_b64 = base64.b64encode(test_content.encode()).decode()

    webhook_payload["data"]["attachments"] = [
        {
            "name": "test.txt",
            "type": "text/plain",
            "content": test_content_b64,
            "size": len(test_content),
        }
    ]

    # When we parse it
    # In tests, we're using a Dict directly instead of a Request object
    result = await webhook_client.parse_webhook(webhook_payload)  # type: ignore

    # Then it should include the attachments
    assert result.data is not None
    assert hasattr(result.data, "attachments")
    assert len(result.data.attachments) == 1
    assert result.data.attachments[0].name == "test.txt"
    assert result.data.attachments[0].type == "text/plain"
