"""Unit tests for the WebhookClient."""

import pytest
from fastapi import HTTPException

from app.integrations.email.client import WebhookClient
from app.schemas.webhook_schemas import WebhookData


def test_webhook_client_init() -> None:
    """Test WebhookClient initialization."""
    # Test data
    api_key = "test_api_key"
    webhook_secret = "test_webhook_secret"

    # Initialize client
    client = WebhookClient(api_key=api_key, webhook_secret=webhook_secret)

    # Verify
    assert client.api_key == api_key
    assert client.webhook_secret == webhook_secret
    assert client.base_url == "https://us1.api.mailchimp.com/3.0"


@pytest.mark.asyncio
async def test_parse_webhook_valid() -> None:
    """Test parsing a valid webhook."""
    # Test data
    webhook_data = {
        "webhook_id": "test_id",
        "event": "inbound_email",
        "timestamp": "2023-01-01T12:00:00Z",
        "data": {
            "message_id": "test_message_id",
            "from_email": "sender@example.com",
            "to_email": "recipient@example.com",
            "subject": "Test Subject",
            "body_plain": "Test body",
            "headers": {},
            "attachments": [],
        },
    }

    # Initialize client
    client = WebhookClient(api_key="test_api_key", webhook_secret="test_secret")

    # Parse webhook directly with the webhook data
    result = await client.parse_webhook(webhook_data)

    # Assertions
    assert isinstance(result, WebhookData)
    assert result.webhook_id == webhook_data["webhook_id"]
    assert result.event == webhook_data["event"]

    # Check data field properties
    message_id = webhook_data["data"]["message_id"]
    assert result.data.message_id == message_id


@pytest.mark.asyncio
async def test_parse_webhook_invalid_payload() -> None:
    """Test parsing a webhook with invalid payload."""
    # Invalid data
    invalid_data = {"invalid": "data"}

    # Initialize client
    client = WebhookClient(api_key="test_api_key", webhook_secret="test_secret")

    # Assert that HTTPException is raised
    with pytest.raises(HTTPException) as excinfo:
        await client.parse_webhook(invalid_data)

    # Verify exception details
    assert excinfo.value.status_code == 400
    assert "Invalid webhook payload" in excinfo.value.detail


@pytest.mark.asyncio
async def test_parse_webhook_valid_with_type() -> None:
    """Test parsing a valid webhook with type."""
    # Test data
    webhook_data = {
        "webhook_id": "test_id",
        "event": "inbound_email",
        "timestamp": "2023-01-01T12:00:00Z",
        "type": "test_type",
        "data": {
            "message_id": "test_message_id",
            "from_email": "sender@example.com",
            "to_email": "recipient@example.com",
            "subject": "Test Subject",
            "body_plain": "Test body",
            "headers": {},
            "attachments": [],
        },
    }

    # Initialize client
    client = WebhookClient(api_key="test_api_key", webhook_secret="test_secret")

    # Parse webhook
    result = await client.parse_webhook(webhook_data)

    # Assertions
    assert isinstance(result, WebhookData)
    assert result.webhook_id == webhook_data["webhook_id"]
    assert result.event == webhook_data["event"]
    # Type isn't a standard field in WebhookData, so we don't check it
    message_id = webhook_data["data"]["message_id"]
    assert result.data.message_id == message_id
