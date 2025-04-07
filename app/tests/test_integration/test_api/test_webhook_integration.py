"""Integration tests for the webhooks API endpoints."""

from datetime import datetime
from typing import Any, Dict
from unittest import mock

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.email.models import MailchimpWebhook as ModelsMailchimpWebhook
from app.models.email_data import Attachment, Email
from app.schemas.webhook_schemas import EmailAttachment as SchemaEmailAttachment
from app.schemas.webhook_schemas import InboundEmailData, MailchimpWebhook
from app.services.email_processing_service import EmailProcessingService


def create_test_webhook_payload(with_attachment: bool = False) -> Dict[str, Any]:
    """Create a test webhook payload for testing."""
    data = {
        "message_id": "test-123@example.com",
        "from_email": "sender@example.com",
        "from_name": "Test Sender",
        "to_email": "recipient@kave.com",
        "subject": "Test Email Subject",
        "body_plain": "This is a test email body.",
        "body_html": "<html><body><p>This is a test email body.</p></body></html>",
        "headers": {
            "From": "Test Sender <sender@example.com>",
            "To": "recipient@kave.com",
            "Subject": "Test Email Subject",
        },
        "attachments": [],
    }

    # Create webhook payload
    webhook_payload = {
        "webhook_id": "test-webhook-123",
        "event": "inbound_email",
        "timestamp": datetime.utcnow().isoformat(),
        "data": data,
    }

    return webhook_payload


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
    service = EmailProcessingService(db_session)
    with mock.patch(
        "app.services.email_processing_service.ATTACHMENTS_DIR",
        mock.MagicMock(return_value="./data/test_attachments"),
    ):
        email = await service.process_webhook(schema_webhook)

    # THEN
    assert email is not None
    assert email.webhook_id == webhook_payload["webhook_id"]
    assert email.webhook_event == webhook_payload["event"]
    assert email.message_id == webhook_payload["data"]["message_id"]

    # Verify it was saved in the database
    query = select(Email).where(Email.webhook_id == webhook_payload["webhook_id"])
    result = await db_session.execute(query)
    stored_email = result.scalar_one_or_none()

    assert stored_email is not None
    assert stored_email.id == email.id


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
    service = EmailProcessingService(db_session)
    with mock.patch(
        "app.services.email_processing_service.ATTACHMENTS_DIR",
        mock.MagicMock(return_value="./data/test_attachments"),
    ):
        # Process the webhook with mock file operations
        with mock.patch("builtins.open", mock.mock_open()):
            email = await service.process_webhook(schema_webhook)

    # THEN
    assert email is not None
    assert email.message_id == schema_webhook.data.message_id

    # Verify the email was saved
    query = select(Email).where(Email.message_id == schema_webhook.data.message_id)
    result = await db_session.execute(query)
    stored_email = result.scalar_one_or_none()
    assert stored_email is not None

    # Query for the attachments separately
    query = select(Attachment).where(Attachment.email_id == stored_email.id)
    result = await db_session.execute(query)
    attachments = result.scalars().all()

    # Verify the attachment was saved
    assert len(attachments) == 1
    assert attachments[0].filename == "test.txt"
    assert attachments[0].content_type == "text/plain"


@pytest.mark.asyncio
async def test_email_processing_service(
    db_session: AsyncSession, setup_db: Any
) -> None:
    """Test the EmailProcessingService directly."""
    # GIVEN
    service = EmailProcessingService(db_session)
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
    with mock.patch(
        "app.services.email_processing_service.ATTACHMENTS_DIR",
        mock.MagicMock(return_value="./data/test_attachments"),
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
    stored_email = result.scalar_one_or_none()

    assert stored_email is not None
    assert stored_email.id == email.id


@pytest.mark.asyncio
async def test_error_handling_in_service(
    db_session: AsyncSession, setup_db: Any
) -> None:
    """Test error handling in the email processing service."""
    # GIVEN
    service = EmailProcessingService(db_session)
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

    # To ensure test integrity, delete any existing emails with this message_id
    # This makes the test more reliable
    delete_stmt = delete(Email).where(
        Email.message_id == schema_webhook.data.message_id
    )
    await db_session.execute(delete_stmt)
    await db_session.commit()

    # WHEN/THEN - Simulate a database error
    with mock.patch.object(
        service, "store_email", side_effect=Exception("Test database error")
    ):
        with pytest.raises(
            ValueError, match="Email processing failed:.*Test database error"
        ):
            await service.process_webhook(schema_webhook)

        # Verify no email was saved by counting emails with this message_id
        count_query = (
            select(func.count())
            .select_from(Email)
            .where(Email.message_id == schema_webhook.data.message_id)
        )
        result = await db_session.execute(count_query)
        count = result.scalar_one()
        assert count == 0
