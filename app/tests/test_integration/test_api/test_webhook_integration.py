"""Integration tests for the webhooks API endpoints."""

import base64
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest import mock

import httpx
import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient
from pytest_mock import MockerFixture
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.email.models import MailchimpWebhook as ModelsMailchimpWebhook
from app.main import create_application
from app.models.email_data import Attachment, Email
from app.schemas.webhook_schemas import EmailAttachment as SchemaEmailAttachment
from app.schemas.webhook_schemas import InboundEmailData, WebhookData
from app.services.attachment_service import AttachmentService
from app.services.email_service import EmailService
from app.services.storage_service import StorageService

# Path to the email service for mocking
EMAIL_SERVICE_PATH = "app.services.email_service.EmailService"


def create_test_webhook_payload(with_attachment: bool = False) -> dict[str, Any]:
    """Create a test webhook payload."""
    message_id = f"test_{uuid.uuid4()}@example.com"
    webhook_id = f"test_webhook_{uuid.uuid4()}"

    data: dict[str, Any] = {
        "message_id": message_id,
        "from_email": "sender@example.com",
        "from_name": "Test Sender",
        "to_email": "webhook@kave.com",
        "subject": "Test Email",
        "body_plain": "This is a test email",
        "body_html": "<p>This is a test email</p>",
        "headers": {"Reply-To": "sender@example.com"},
    }

    if with_attachment:
        test_content = "This is a test attachment"
        test_content_b64 = base64.b64encode(test_content.encode()).decode()

        data["attachments"] = [
            {
                "name": "test.txt",
                "type": "text/plain",
                "content": test_content_b64,
                "content_id": "test001",
                "size": len(test_content),
            }
        ]
    else:
        data["attachments"] = []

    return {
        "webhook_id": webhook_id,
        "event": "inbound_email",
        "timestamp": datetime.utcnow().isoformat(),
        "data": data,
    }


def create_ping_event() -> dict[str, Any]:
    """Create a test ping event payload for webhook registration."""
    return {
        "type": "ping",
        "event": "ping",
        "webhook_id": f"test_webhook_{uuid.uuid4()}",
        "timestamp": datetime.utcnow().isoformat(),
    }


@pytest.fixture
def app() -> FastAPI:
    """Create a test application instance."""
    return create_application()


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """Create a test client for the application."""
    return TestClient(app)


@pytest.mark.asyncio
async def test_webhook_endpoint_success(
    db_session: AsyncSession, setup_db: Any
) -> None:
    """Test successful webhook processing through the API endpoint."""
    # GIVEN
    webhook_payload = create_test_webhook_payload()

    # WHEN - We convert the webhook to MailchimpWebhook first for type safety
    webhook_model = ModelsMailchimpWebhook(
        webhook_id=webhook_payload["webhook_id"],
        event=webhook_payload["event"],
        data=webhook_payload["data"],
        fired_at=datetime.fromisoformat(webhook_payload["timestamp"]),
        type="inbound",
        test_mode=False,
    )

    # Extract data as a schema before processing
    if isinstance(webhook_model.data, dict):
        # Handle dictionary data from the payload
        schema_data = InboundEmailData(**webhook_model.data)
    else:
        # It's already an InboundEmailData object
        schema_data = InboundEmailData(**webhook_model.data.to_dict())

    schema_webhook = WebhookData(
        webhook_id=webhook_model.webhook_id or "",
        event=webhook_model.event or "",
        timestamp=webhook_model.fired_at or datetime.utcnow(),
        data=schema_data,
    )

    # Create service and process
    storage_service = StorageService()
    attachment_service = AttachmentService(db_session, storage_service)
    service = EmailService(db_session, attachment_service, storage_service)
    with (
        mock.patch(
            "app.core.config.settings.ATTACHMENTS_BASE_DIR",
            Path("./data/test_attachments"),
        ),
        mock.patch("builtins.open", mock.mock_open()),
    ):
        email = await service.process_webhook(schema_webhook)

    # THEN
    assert email is not None
    assert email.message_id == schema_webhook.data.message_id
    assert email.from_email == schema_webhook.data.from_email
    assert email.subject == schema_webhook.data.subject

    # Verify it was saved to the database
    query = select(Email).where(Email.message_id == schema_webhook.data.message_id)
    result = await db_session.execute(query)
    db_email = result.scalar_one_or_none()
    assert db_email is not None
    assert db_email.id == email.id


@pytest.mark.asyncio
async def test_webhook_with_attachments(
    db_session: AsyncSession, setup_db: Any
) -> None:
    """Test webhook processing with attachments."""
    # GIVEN
    webhook_payload = create_test_webhook_payload(with_attachment=True)

    # WHEN - We convert the webhook to MailchimpWebhook first for type safety
    webhook_model = ModelsMailchimpWebhook(
        webhook_id=webhook_payload["webhook_id"],
        event=webhook_payload["event"],
        data=webhook_payload["data"],
        fired_at=datetime.fromisoformat(webhook_payload["timestamp"]),
        type="inbound",
        test_mode=False,
    )

    # Extract data as a schema before processing
    if isinstance(webhook_model.data, dict):
        # Handle dictionary data from the payload
        schema_data = InboundEmailData(**webhook_model.data)
    else:
        # It's already an InboundEmailData object
        schema_data = InboundEmailData(**webhook_model.data.to_dict())

    # Add the attachment directly to the schema
    schema_data.attachments.append(
        SchemaEmailAttachment(
            name="test.txt",
            type="text/plain",
            content="VGhpcyBpcyBhIHRlc3QgZmlsZQ==",  # "This is a test file" in base64
            content_id="test123",
            size=15,
            base64=True,
        )
    )

    schema_webhook = WebhookData(
        webhook_id=webhook_model.webhook_id or "",
        event=webhook_model.event or "",
        timestamp=webhook_model.fired_at or datetime.utcnow(),
        data=schema_data,
    )

    # Create service and process
    storage_service = StorageService()
    attachment_service = AttachmentService(db_session, storage_service)
    service = EmailService(db_session, attachment_service, storage_service)
    with (
        mock.patch(
            "app.core.config.settings.ATTACHMENTS_BASE_DIR",
            Path("./data/test_attachments"),
        ),
        # Mock the S3 storage operation directly to avoid AWS client issues
        mock.patch.object(
            storage_service,
            "_save_to_s3",
            new=mock.AsyncMock(
                return_value="s3://test-bucket/attachments/test-file.txt"
            ),
        ),
        # Make sure we're using S3 storage for this test
        mock.patch("app.core.config.settings.USE_S3_STORAGE", True),
        mock.patch("builtins.open", mock.mock_open()),
    ):
        email = await service.process_webhook(schema_webhook)

    # THEN
    assert email is not None
    assert email.message_id == schema_webhook.data.message_id
    assert len(schema_webhook.data.attachments) > 0  # Confirm attachment was included

    # Verify it was saved to the database with attachments
    query = select(Email).where(Email.message_id == schema_webhook.data.message_id)
    result = await db_session.execute(query)
    db_email = result.scalar_one_or_none()
    assert db_email is not None

    # Verify attachments
    attachment_query = select(Attachment).where(Attachment.email_id == db_email.id)
    attachment_result = await db_session.execute(attachment_query)
    attachments = attachment_result.scalars().all()
    assert len(attachments) > 0
    assert attachments[0].filename == "test.txt"
    assert attachments[0].content_type == "text/plain"
    assert attachments[0].storage_uri is not None
    assert "s3://" in attachments[0].storage_uri


@pytest.mark.asyncio
async def test_email_processing_service(
    db_session: AsyncSession, setup_db: Any
) -> None:
    """Test the EmailService directly."""
    # GIVEN
    storage_service = StorageService()
    attachment_service = AttachmentService(db_session, storage_service)
    service = EmailService(db_session, attachment_service, storage_service)
    webhook_payload = create_test_webhook_payload()

    webhook_model = ModelsMailchimpWebhook(
        webhook_id=webhook_payload["webhook_id"],
        event=webhook_payload["event"],
        data=webhook_payload["data"],
        fired_at=datetime.fromisoformat(webhook_payload["timestamp"]),
        type="inbound",
        test_mode=False,
    )

    # Extract data as a schema before processing
    if isinstance(webhook_model.data, dict):
        # Handle dictionary data from the payload
        schema_data = InboundEmailData(**webhook_model.data)
    else:
        # It's already an InboundEmailData object
        schema_data = InboundEmailData(**webhook_model.data.to_dict())

    # Convert to our schema
    schema_webhook = WebhookData(
        webhook_id=webhook_model.webhook_id or "",
        event=webhook_model.event or "",
        timestamp=webhook_model.fired_at or datetime.utcnow(),
        data=schema_data,
    )

    # WHEN - Process the webhook
    with (
        mock.patch(
            "app.core.config.settings.ATTACHMENTS_BASE_DIR",
            Path("./data/test_attachments"),
        ),
        mock.patch("builtins.open", mock.mock_open()),
    ):
        email = await service.process_webhook(schema_webhook)

    # THEN
    assert email is not None
    assert email.message_id == schema_webhook.data.message_id
    assert email.from_email == schema_webhook.data.from_email
    assert email.subject == schema_webhook.data.subject

    # Verify it was saved to the database
    query = select(Email).where(Email.message_id == schema_webhook.data.message_id)
    result = await db_session.execute(query)
    db_email = result.scalar_one_or_none()
    assert db_email is not None
    assert db_email.id == email.id


@pytest.mark.asyncio
async def test_error_handling_in_service(
    db_session: AsyncSession, setup_db: Any
) -> None:
    """Test error handling in the EmailService."""
    # GIVEN
    storage_service = StorageService()
    attachment_service = AttachmentService(db_session, storage_service)
    service = EmailService(db_session, attachment_service, storage_service)
    webhook_payload = create_test_webhook_payload()

    webhook_model = ModelsMailchimpWebhook(
        webhook_id=webhook_payload["webhook_id"],
        event=webhook_payload["event"],
        data=webhook_payload["data"],
        fired_at=datetime.fromisoformat(webhook_payload["timestamp"]),
        type="inbound",
        test_mode=False,
    )

    # Extract data as a schema before processing
    if isinstance(webhook_model.data, dict):
        # Handle dictionary data from the payload
        schema_data = InboundEmailData(**webhook_model.data)
    else:
        # It's already an InboundEmailData object
        schema_data = InboundEmailData(**webhook_model.data.to_dict())

    # Create the webhook with schema
    schema_webhook = WebhookData(
        webhook_id=webhook_model.webhook_id or "",
        event=webhook_model.event or "",
        timestamp=webhook_model.fired_at or datetime.utcnow(),
        data=schema_data,
    )

    # Make store_email raise an exception
    with (
        mock.patch.object(
            service, "store_email", side_effect=ValueError("Simulated error")
        ),
    ):
        # WHEN/THEN
        with pytest.raises(ValueError, match="Email processing failed"):
            await service.process_webhook(schema_webhook)

    # Verify transaction was rolled back
    query = select(Email).where(Email.message_id == schema_webhook.data.message_id)
    result = await db_session.execute(query)
    db_email = result.scalar_one_or_none()
    assert db_email is None  # Transaction rolled back, so no email saved


@pytest.mark.asyncio
async def test_webhook_endpoint_ping(
    async_client: httpx.AsyncClient, mocker: MockerFixture
) -> None:
    """Test webhook endpoint handling of Mailchimp ping events."""
    # Create a ping event payload
    ping_payload = create_ping_event()

    # Mock the ping detection function to ensure it returns True
    mocker.patch(
        "app.api.v1.endpoints.webhooks.mandrill.parsers._is_ping_event",
        return_value=True,
    )

    # Mock the organization identification to avoid DB errors
    mocker.patch(
        "app.integrations.email.client.WebhookClient.identify_organization_by_signature",
        return_value=(None, False),
    )

    # Send the webhook request
    response = await async_client.post(
        "/v1/webhooks/mandrill",
        headers={"X-Mailchimp-Signature": "test-signature"},
        json=ping_payload,
    )

    # Verify the response - should be 202 Accepted for ping events
    assert response.status_code == status.HTTP_202_ACCEPTED
    assert response.json() == {
        "status": "success",
        "message": "Ping acknowledged",
    }
