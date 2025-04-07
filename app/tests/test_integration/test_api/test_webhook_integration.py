"""Integration tests for the webhooks API endpoints."""

import base64
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict
from unittest import mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.email.models import MailchimpWebhook as ModelsMailchimpWebhook
from app.main import create_application
from app.models.email_data import Attachment, Email
from app.schemas.webhook_schemas import EmailAttachment as SchemaEmailAttachment
from app.schemas.webhook_schemas import InboundEmailData, MailchimpWebhook
from app.services.email_processing_service import EmailProcessingService
from app.services.storage_service import StorageService


def create_test_webhook_payload(with_attachment: bool = False) -> Dict[str, Any]:
    """Create a test webhook payload."""
    message_id = f"test_{uuid.uuid4()}@example.com"
    webhook_id = f"test_webhook_{uuid.uuid4()}"

    data: Dict[str, Any] = {
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
    )

    # Extract data as a schema before processing
    if isinstance(webhook_model.data, dict):
        # Handle dictionary data from the payload
        schema_data = InboundEmailData(**webhook_model.data)
    else:
        # It's already an InboundEmailData object
        schema_data = InboundEmailData(**webhook_model.data.to_dict())

    schema_webhook = MailchimpWebhook(
        webhook_id=webhook_model.webhook_id or "",
        event=webhook_model.event or "",
        timestamp=webhook_model.fired_at or datetime.utcnow(),
        data=schema_data,
    )

    # Create service and process
    storage_service = StorageService()
    service = EmailProcessingService(db_session, storage_service)
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
        )
    )

    schema_webhook = MailchimpWebhook(
        webhook_id=webhook_model.webhook_id or "",
        event=webhook_model.event or "",
        timestamp=webhook_model.fired_at or datetime.utcnow(),
        data=schema_data,
    )

    # Create service and process
    storage_service = StorageService()
    service = EmailProcessingService(db_session, storage_service)
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


@pytest.mark.asyncio
async def test_email_processing_service(
    db_session: AsyncSession, setup_db: Any
) -> None:
    """Test the EmailProcessingService directly."""
    # GIVEN
    storage_service = StorageService()
    service = EmailProcessingService(db_session, storage_service)
    webhook_payload = create_test_webhook_payload()

    # Create a webhook object with proper types
    webhook_model = ModelsMailchimpWebhook(
        webhook_id=webhook_payload["webhook_id"],
        event=webhook_payload["event"],
        data=webhook_payload["data"],
        fired_at=datetime.fromisoformat(webhook_payload["timestamp"]),
    )

    # Extract data as a schema before processing
    if isinstance(webhook_model.data, dict):
        # Handle dictionary data from the payload
        schema_data = InboundEmailData(**webhook_model.data)
    else:
        # It's already an InboundEmailData object
        schema_data = InboundEmailData(**webhook_model.data.to_dict())

    schema_webhook = MailchimpWebhook(
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
    """Test error handling in the email processing service."""
    # GIVEN
    storage_service = StorageService()
    service = EmailProcessingService(db_session, storage_service)
    webhook_payload = create_test_webhook_payload()

    # Create a webhook object with proper types
    webhook_model = ModelsMailchimpWebhook(
        webhook_id=webhook_payload["webhook_id"],
        event=webhook_payload["event"],
        data=webhook_payload["data"],
        fired_at=datetime.fromisoformat(webhook_payload["timestamp"]),
    )

    # Extract data as a schema before processing
    if isinstance(webhook_model.data, dict):
        # Handle dictionary data from the payload
        schema_data = InboundEmailData(**webhook_model.data)
    else:
        # It's already an InboundEmailData object
        schema_data = InboundEmailData(**webhook_model.data.to_dict())

    schema_webhook = MailchimpWebhook(
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
