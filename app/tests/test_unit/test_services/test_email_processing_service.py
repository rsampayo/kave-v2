"""Unit tests for EmailService."""

from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.email_data import Attachment, Email, EmailAttachment
from app.schemas.webhook_schemas import EmailAttachment as SchemaEmailAttachment
from app.schemas.webhook_schemas import InboundEmailData, MailchimpWebhook
from app.services.attachment_service import AttachmentService
from app.services.email_service import EmailService, get_email_service
from app.services.storage_service import StorageService


def create_test_webhook() -> MailchimpWebhook:
    """Create a test webhook for unit tests."""
    return MailchimpWebhook(
        webhook_id="test-webhook-123",
        event="inbound_email",
        timestamp=datetime.utcnow(),
        data=InboundEmailData(
            message_id="test-123@example.com",
            from_email="sender@example.com",
            from_name="Test Sender",
            to_email="recipient@kave.com",
            subject="Test Subject",
            body_plain="This is a test body",
            body_html="<p>This is a test body</p>",
            headers={"From": "sender@example.com", "To": "recipient@kave.com"},
            attachments=[],
        ),
    )


# Helper function to convert schema attachment to model attachment
def schema_to_model_attachment(
    schema_attachment: SchemaEmailAttachment,
) -> EmailAttachment:
    """Convert schema EmailAttachment to model EmailAttachment."""
    return EmailAttachment(
        name=schema_attachment.name,
        type=schema_attachment.type,
        content=schema_attachment.content or "",
        content_id=schema_attachment.content_id,
        size=schema_attachment.size,
        base64=True,
    )


@pytest.fixture
def mock_storage_service() -> AsyncMock:
    """Create a mock storage service for tests."""
    mock = AsyncMock(spec=StorageService)
    mock.save_file.return_value = "file:///test/path/to/file.txt"
    return mock


@pytest.fixture
def mock_attachment_service(mock_storage_service: AsyncMock) -> AsyncMock:
    """Create a mock attachment service for tests."""
    mock = AsyncMock(spec=AttachmentService)
    mock.process_attachments.return_value = []
    return mock


@pytest.mark.asyncio
async def test_get_email_service() -> None:
    """Test that get_email_service returns a proper EmailService instance."""
    # Mock database session, attachment service, and storage service
    mock_db = MagicMock(spec=AsyncSession)
    mock_attachment = MagicMock(spec=AttachmentService)
    mock_storage = MagicMock(spec=StorageService)

    # Get service from dependency function
    service = await get_email_service(mock_db, mock_attachment, mock_storage)

    # Verify service was created with the right dependencies
    assert isinstance(service, EmailService)
    assert service.db == mock_db
    assert service.attachment_service == mock_attachment
    assert service.storage == mock_storage


@pytest.mark.asyncio
async def test_store_email(
    db_session: AsyncSession,
    mock_storage_service: AsyncMock,
    mock_attachment_service: AsyncMock,
    setup_db: Any,
) -> None:
    """Test storing an email in the database."""
    # GIVEN
    # Create a custom db_session that properly handles mock behavior
    session_mock = MagicMock(spec=AsyncSession)

    # Create a result mock for execute to return
    result_mock = MagicMock()
    result_mock.scalar_one_or_none = MagicMock(return_value=None)  # No existing email

    # Set up the session mock with awaitable methods
    session_mock.execute = AsyncMock(return_value=result_mock)
    session_mock.add = MagicMock()  # Regular MagicMock for add (not async)
    session_mock.flush = AsyncMock()

    service = EmailService(session_mock, mock_attachment_service, mock_storage_service)
    email_data = InboundEmailData(
        message_id="test123@example.com",
        from_email="sender@example.com",
        from_name="Test Sender",
        to_email="receiver@kave.com",
        subject="Test Email",
        body_plain="This is a test email",
        body_html="<p>This is a test email</p>",
        headers={},
        attachments=[],
    )
    webhook_id = "webhook123"
    event = "inbound_email"

    # WHEN
    email = await service.store_email(email_data, webhook_id, event)

    # THEN
    assert email is not None
    assert email.message_id == "test123@example.com"
    assert email.from_email == "sender@example.com"
    assert email.from_name == "Test Sender"
    assert email.to_email == "receiver@kave.com"
    assert email.subject == "Test Email"
    assert email.body_text == "This is a test email"
    assert email.body_html == "<p>This is a test email</p>"
    assert email.webhook_id == webhook_id
    assert email.webhook_event == event

    # Verify it was added to the session
    session_mock.add.assert_called_once()
    session_mock.flush.assert_awaited_once()
    session_mock.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_webhook_basic(
    db_session: AsyncSession,
    mock_storage_service: AsyncMock,
    mock_attachment_service: AsyncMock,
    setup_db: Any,
) -> None:
    """Test basic webhook processing."""
    # GIVEN
    service = EmailService(db_session, mock_attachment_service, mock_storage_service)
    webhook = create_test_webhook()

    # WHEN
    email = await service.process_webhook(webhook)

    # THEN
    assert email is not None
    assert email.message_id == webhook.data.message_id
    assert email.from_email == webhook.data.from_email
    assert email.from_name == webhook.data.from_name
    assert email.to_email == webhook.data.to_email
    assert email.subject == webhook.data.subject
    assert email.webhook_id == webhook.webhook_id
    assert email.webhook_event == webhook.event


@pytest.mark.asyncio
async def test_process_webhook_with_attachments(
    db_session: AsyncSession,
    mock_storage_service: AsyncMock,
    mock_attachment_service: AsyncMock,
    setup_db: Any,
) -> None:
    """Test webhook processing with attachments."""
    # GIVEN
    service = EmailService(db_session, mock_attachment_service, mock_storage_service)
    webhook = create_test_webhook()

    # Add an attachment to the webhook data
    webhook.data.attachments.append(
        SchemaEmailAttachment(
            name="test.txt",
            type="text/plain",
            content="VGhpcyBpcyBhIHRlc3QgZmlsZQ==",  # "This is a test file" in base64
            content_id="test123",
            size=15,
            base64=True,
        )
    )

    # Set up a mock for attachment processing
    test_attachment = Attachment(
        id=1,
        email_id=1,
        filename="test.txt",
        content_type="text/plain",
        storage_uri="file:///test/path/to/attachment.txt",
    )
    mock_attachment_service.process_attachments.return_value = [test_attachment]

    # WHEN
    email = await service.process_webhook(webhook)

    # THEN
    assert email is not None
    assert email.message_id == webhook.data.message_id

    # Verify attachment service was called with correct parameters
    mock_attachment_service.process_attachments.assert_awaited_once()
    assert mock_attachment_service.process_attachments.call_args[0][0] == email.id
    assert len(mock_attachment_service.process_attachments.call_args[0][1]) == 1
    assert (
        mock_attachment_service.process_attachments.call_args[0][1][0].name
        == "test.txt"
    )


@pytest.mark.asyncio
async def test_process_webhook_error_handling(
    mock_storage_service: AsyncMock,
    mock_attachment_service: AsyncMock,
) -> None:
    """Test error handling during webhook processing."""
    # GIVEN
    # Create a mocked session that can track calls
    mock_db_session = MagicMock(spec=AsyncSession)
    mock_db_session.rollback = AsyncMock()

    service = EmailService(
        mock_db_session, mock_attachment_service, mock_storage_service
    )
    webhook = create_test_webhook()

    # Setup mock for attachment service to fail
    mock_attachment_service.process_attachments.side_effect = RuntimeError("Test error")

    # Add an attachment to the webhook data
    webhook.data.attachments.append(
        SchemaEmailAttachment(
            name="test.txt",
            type="text/plain",
            content="VGhpcyBpcyBhIHRlc3QgZmlsZQ==",
            content_id="test123",
            size=15,
            base64=True,
        )
    )

    # WHEN/THEN
    with pytest.raises(ValueError):
        await service.process_webhook(webhook)

    # Verify rollback was called
    mock_db_session.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_duplicate_email_handling(
    db_session: AsyncSession,
    mock_storage_service: AsyncMock,
    mock_attachment_service: AsyncMock,
    setup_db: Any,
) -> None:
    """Test handling of duplicate emails."""
    # GIVEN
    service = EmailService(db_session, mock_attachment_service, mock_storage_service)
    webhook = create_test_webhook()

    # First call to store the email
    email1 = await service.process_webhook(webhook)
    await db_session.commit()

    # Reset the session
    await db_session.close()

    # Second call with the same message_id should find the existing email
    email2 = await service.process_webhook(webhook)

    # THEN
    assert email1.id == email2.id
    assert email1.message_id == email2.message_id


@pytest.mark.asyncio
async def test_get_email_by_message_id(
    db_session: AsyncSession,
    mock_storage_service: AsyncMock,
    mock_attachment_service: AsyncMock,
    setup_db: Any,
) -> None:
    """Test retrieving an email by message ID."""
    # GIVEN
    service = EmailService(db_session, mock_attachment_service, mock_storage_service)

    # Create a test email
    email = Email(
        message_id="test-retrieve@example.com",
        from_email="sender@example.com",
        from_name="Test Sender",
        to_email="recipient@kave.com",
        subject="Test Retrieval",
        body_text="This is a test for retrieval",
        received_at=datetime.utcnow(),
    )
    db_session.add(email)
    await db_session.flush()
    await db_session.commit()

    # Reset session
    await db_session.close()

    # WHEN
    found_email = await service.get_email_by_message_id("test-retrieve@example.com")

    # THEN
    assert found_email is not None
    assert found_email.message_id == "test-retrieve@example.com"
    assert found_email.subject == "Test Retrieval"

    # Test non-existent email
    not_found = await service.get_email_by_message_id("non-existent@example.com")
    assert not_found is None
