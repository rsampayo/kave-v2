"""End-to-end tests for the webhook processing flow."""

import base64
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict
from unittest import mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from app.main import create_application


def create_test_webhook_payload() -> Dict[str, Any]:
    """Create a test webhook payload with an attachment."""
    # Create a test attachment
    test_content = "This is a test attachment"
    test_content_b64 = base64.b64encode(test_content.encode()).decode()

    # Use a unique message ID for each test run
    message_id = f"e2e_test_{uuid.uuid4()}@example.com"

    return {
        "webhook_id": f"e2e_webhook_{uuid.uuid4()}",
        "event": "inbound_email",
        "timestamp": datetime.utcnow().isoformat(),
        "data": {
            "message_id": message_id,
            "from_email": "sender@example.com",
            "from_name": "E2E Test Sender",
            "to_email": "webhook@kave.com",
            "subject": "E2E Test Email",
            "body_plain": "This is an end-to-end test email",
            "body_html": "<p>This is an end-to-end test email</p>",
            "headers": {"Reply-To": "sender@example.com"},
            "attachments": [
                {
                    "name": "e2e_test.txt",
                    "type": "text/plain",
                    "content": test_content_b64,
                    "content_id": "e2e_att001",
                    "size": len(test_content),
                }
            ],
        },
    }


@pytest.fixture
def webhook_signature() -> str:
    """Create a valid webhook signature for testing."""
    # This will be patched in the tests
    return "valid_signature_for_testing"


@pytest.fixture
def app() -> FastAPI:
    """Create a test application instance."""
    return create_application()


@pytest.fixture
def test_client(app: FastAPI) -> TestClient:
    """Create a test client for the application."""
    return TestClient(app)


@pytest.mark.asyncio
async def test_webhook_e2e_flow(app: FastAPI, webhook_signature: str) -> None:
    """Test the full webhook processing flow from end to end."""
    # GIVEN
    webhook_payload = create_test_webhook_payload()

    # Create a test directory for attachments
    test_attachments_dir = Path("test_e2e_attachments")
    test_attachments_dir.mkdir(exist_ok=True, parents=True)

    try:
        # Setup the patches we need for the test
        with (
            mock.patch(
                "app.integrations.email.client.MailchimpClient."
                "verify_webhook_signature",
                return_value=True,
            ),
            mock.patch(
                "app.core.config.settings.ATTACHMENTS_BASE_DIR",
                test_attachments_dir,
            ),
            # Disable S3 for this test and use local filesystem instead
            mock.patch(
                "app.core.config.settings.USE_S3_STORAGE",
                False,
            ),
            # In case S3 is still accessed, mock the S3 client creation
            mock.patch(
                "app.services.storage_service.StorageService._save_to_s3",
                new=mock.AsyncMock(return_value="s3://test-bucket/test-object"),
            ),
            mock.patch("builtins.open", mock.mock_open()),
        ):
            # Create an async client for making the request
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                # WHEN - Send a POST request to the webhook endpoint
                response = await client.post(
                    "/webhooks/mailchimp",
                    json=webhook_payload,
                    headers={"X-Mailchimp-Signature": webhook_signature},
                )

        # THEN - Check the response
        assert (
            response.status_code == 202
        ), f"Expected status code 202, got {response.status_code}"
        json_response = response.json()
        assert (
            json_response["status"] == "success"
        ), f"Expected status 'success', got {json_response['status']}"

        # Log the result for easier debugging
        print(
            f"Webhook processed successfully with message ID: "
            f"{webhook_payload['data']['message_id']}"
        )

    finally:
        # Clean up
        if test_attachments_dir.exists():
            import shutil

            shutil.rmtree(test_attachments_dir)


@pytest.mark.asyncio
async def test_webhook_e2e_invalid_signature(
    app: FastAPI, webhook_signature: str
) -> None:
    """Test the webhook flow with an invalid signature."""
    # GIVEN
    webhook_payload = create_test_webhook_payload()

    # Setup signature verification to fail
    with mock.patch(
        "app.integrations.email.client.MailchimpClient.verify_webhook_signature",
        return_value=False,
    ):
        # WHEN - Send a POST request to the webhook endpoint
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/webhooks/mailchimp",
                json=webhook_payload,
                headers={"X-Mailchimp-Signature": "invalid_signature"},
            )

    # THEN - Check that the request was processed successfully despite invalid signature
    assert response.status_code == 202  # Accepted
    assert "success" in response.json()["status"]


@pytest.mark.asyncio
async def test_webhook_e2e_invalid_data(app: FastAPI, webhook_signature: str) -> None:
    """Test the webhook flow with invalid data."""
    # GIVEN - Invalid webhook data (not JSON)
    invalid_data = "This is not JSON"

    # Bypass signature verification
    with mock.patch(
        "app.integrations.email.client.MailchimpClient.verify_webhook_signature",
        return_value=True,
    ):
        # WHEN - Send a POST request with invalid data
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/webhooks/mailchimp",
                content=invalid_data,
                headers={
                    "X-Mailchimp-Signature": webhook_signature,
                    "Content-Type": "text/plain",
                },
            )

    # THEN - Check that the request was handled with an error
    assert response.status_code == 400  # Bad Request
    assert "error" in response.json()["status"].lower()
