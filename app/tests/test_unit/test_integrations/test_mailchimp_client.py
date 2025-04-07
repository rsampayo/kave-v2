"""Unit tests for the Mailchimp client integration."""

import base64
from datetime import datetime
from typing import Any, Dict
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.integrations.email.client import MailchimpClient


@pytest.fixture
def mailchimp_client() -> MailchimpClient:
    """Create a test instance of MailchimpClient."""
    return MailchimpClient(
        webhook_secret="test_secret", api_key="test_key-us1", server_prefix="us1"
    )


@pytest.fixture
def webhook_payload() -> Dict[str, Any]:
    """Create a test webhook payload."""
    return {
        "webhook_id": "test-webhook-123",
        "event": "inbound_email",
        "timestamp": datetime.utcnow().isoformat(),
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


@pytest.mark.asyncio
async def test_verify_webhook_signature_valid(
    mailchimp_client: MailchimpClient,
) -> None:
    """Test webhook signature verification with valid signature."""
    # Given a valid signature
    signature = "valid_signature"

    # When we verify it
    with patch("app.integrations.email.client.hmac.compare_digest", return_value=True):
        # In tests, we're mocking with a string instead of a Request object
        result = await mailchimp_client.verify_webhook_signature(
            signature
        )  # type: ignore

    # Then it should be valid
    assert result is True


@pytest.mark.asyncio
async def test_verify_webhook_signature_invalid(
    mailchimp_client: MailchimpClient,
) -> None:
    """Test webhook signature verification with invalid signature."""
    # Given an invalid signature
    signature = "invalid_signature"

    # When we verify it
    with patch("app.integrations.email.client.hmac.compare_digest", return_value=False):
        # In tests, we're mocking with a string instead of a Request object
        result = await mailchimp_client.verify_webhook_signature(
            signature
        )  # type: ignore

    # Then it should be invalid
    assert result is False


@pytest.mark.asyncio
async def test_verify_webhook_signature_missing(
    mailchimp_client: MailchimpClient,
) -> None:
    """Test webhook signature verification with missing signature."""
    # Given a missing signature
    signature = None

    # When we verify it
    # In tests, we're mocking with None instead of a Request object
    result = await mailchimp_client.verify_webhook_signature(signature)  # type: ignore

    # Then it should be invalid
    assert result is False


@pytest.mark.asyncio
async def test_parse_webhook_valid(
    mailchimp_client: MailchimpClient, webhook_payload: Dict[str, Any]
) -> None:
    """Test parsing a valid webhook payload."""
    # When we parse the webhook
    # In tests, we're using a Dict directly instead of a Request object
    result = await mailchimp_client.parse_webhook(webhook_payload)  # type: ignore

    # Then it should contain the expected fields
    assert result.webhook_id == webhook_payload["webhook_id"]
    assert result.event == webhook_payload["event"]
    assert isinstance(result.timestamp, datetime)
    assert result.data is not None


@pytest.mark.asyncio
async def test_parse_webhook_invalid_event(
    mailchimp_client: MailchimpClient, webhook_payload: Dict[str, Any]
) -> None:
    """Test parsing a webhook with invalid event type."""
    # Given an invalid event type
    webhook_payload["event"] = "invalid_event"

    # When we try to parse it
    with pytest.raises(HTTPException) as exc_info:
        # In tests, we're using a Dict directly instead of a Request object
        await mailchimp_client.parse_webhook(webhook_payload)  # type: ignore

    # Then it should raise an error
    assert exc_info.value.status_code == 400
    assert "Unsupported webhook event" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_parse_webhook_missing_data(
    mailchimp_client: MailchimpClient, webhook_payload: Dict[str, Any]
) -> None:
    """Test parsing a webhook with missing data."""
    # Given missing required data
    del webhook_payload["data"]

    # When we try to parse it
    with pytest.raises(HTTPException) as exc_info:
        # In tests, we're using a Dict directly instead of a Request object
        await mailchimp_client.parse_webhook(webhook_payload)  # type: ignore

    # Then it should raise an error
    assert exc_info.value.status_code == 400
    assert "payload" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_parse_webhook_with_attachments(
    mailchimp_client: MailchimpClient, webhook_payload: Dict[str, Any]
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
    result = await mailchimp_client.parse_webhook(webhook_payload)  # type: ignore

    # Then it should include the attachments
    assert result.data is not None
    assert hasattr(result.data, "attachments")
    assert len(result.data.attachments) == 1
    assert result.data.attachments[0].name == "test.txt"
    assert result.data.attachments[0].type == "text/plain"


@pytest.mark.asyncio
async def test_parse_webhook_with_invalid_attachment(
    mailchimp_client: MailchimpClient, webhook_payload: Dict[str, Any]
) -> None:
    """Test parsing a webhook with invalid attachment data."""
    # Given a webhook with invalid attachment data
    webhook_payload["data"]["attachments"] = [
        {
            "name": "test.txt",
            # Missing required fields
        }
    ]

    # When we try to parse it
    with pytest.raises(HTTPException) as exc_info:
        # In tests, we're using a Dict directly instead of a Request object
        await mailchimp_client.parse_webhook(webhook_payload)  # type: ignore

    # Then it should raise an error
    assert exc_info.value.status_code == 400
    assert "Invalid attachment data" in str(exc_info.value.detail)
