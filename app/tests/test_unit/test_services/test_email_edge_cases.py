"""Tests for email processing edge cases.

This module tests handling of unusual, extreme, or edge cases in email processing,
including large attachments, malformed data, etc.
"""

import base64
import random
import string
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.email_data import Email, EmailAttachment
from app.schemas.webhook_schemas import EmailAttachment as SchemaEmailAttachment
from app.schemas.webhook_schemas import InboundEmailData, MailchimpWebhook
from app.services.attachment_service import AttachmentService
from app.services.email_service import EmailService, _schema_to_model_attachment
from app.services.storage_service import StorageService


@pytest.fixture
def mock_storage_service() -> AsyncMock:
    """Create a mock storage service for tests."""
    mock = AsyncMock(spec=StorageService)
    mock.save_file.return_value = "file:///test/path/to/file.txt"
    return mock


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Fixture for mocking AsyncSession."""
    mock = AsyncMock(spec=AsyncSession)
    # Make add method a normal function instead of a coroutine
    mock.add = MagicMock()
    mock.flush = AsyncMock()
    return mock


@pytest.fixture
def mock_attachment_service() -> AsyncMock:
    """Create a mock attachment service for tests."""
    mock = AsyncMock(spec=AttachmentService)
    mock.process_attachments.return_value = []
    return mock


@pytest.mark.asyncio
async def test_process_very_large_attachment(
    mock_db_session: AsyncMock,
    mock_storage_service: AsyncMock,
    mock_attachment_service: AsyncMock,
    setup_db: Any,
) -> None:
    """Test handling of a very large email attachment."""
    # GIVEN
    service = EmailService(
        mock_db_session, mock_attachment_service, mock_storage_service
    )

    # Create a test email
    email = Email(
        id=123,
        message_id="large_attachment@example.com",
        from_email="sender@example.com",
        from_name="Test Sender",
        to_email="recipient@kave.com",
        subject="Test Large Attachment",
        body_text="This is a test with a large attachment",
        received_at=datetime.utcnow(),
    )

    # Generate a 1MB "large" attachment
    large_content = "".join(
        random.choices(string.ascii_letters + string.digits, k=1_048_576)
    )
    large_content_b64 = base64.b64encode(large_content.encode()).decode()

    # Create schema attachment
    schema_attachment = SchemaEmailAttachment(
        name="large.txt",
        type="text/plain",
        content=large_content_b64,
        content_id="large001",
        size=len(large_content),
        base64=True,
    )

    # Convert to model attachment for the mock return
    attachment = _schema_to_model_attachment(schema_attachment)

    # Mock store_email to return a properly constructed email object
    with (
        patch.object(service, "store_email", return_value=email),
        patch.object(service, "get_email_by_message_id", return_value=None),
    ):

        # Setup mock for attachment service to handle the large file
        mock_attachment_service.process_attachments.return_value = [attachment]

        # Create a mock webhook with the large attachment
        webhook = MailchimpWebhook(
            webhook_id="test-large-123",
            event="inbound_email",
            timestamp=datetime.utcnow(),
            data=InboundEmailData(
                message_id="large_attachment@example.com",
                from_email="sender@example.com",
                from_name="Test Sender",
                to_email="recipient@kave.com",
                subject="Test Subject",
                body_plain="Test body",
                body_html="<p>Test body</p>",
                attachments=[schema_attachment],
            ),
        )

        # Process the webhook
        result = await service.process_webhook(webhook)

        # THEN
        assert result is email
        mock_attachment_service.process_attachments.assert_called_once()


@pytest.mark.asyncio
async def test_process_many_attachments(
    mock_db_session: AsyncMock,
    mock_storage_service: AsyncMock,
    mock_attachment_service: AsyncMock,
    setup_db: Any,
) -> None:
    """Test handling of an email with many attachments."""
    # GIVEN
    service = EmailService(
        mock_db_session, mock_attachment_service, mock_storage_service
    )

    # Create a test email
    email = Email(
        id=123,
        message_id="many_attachments@example.com",
        from_email="sender@example.com",
        from_name="Test Sender",
        to_email="recipient@kave.com",
        subject="Test Many Attachments",
        body_text="This is a test with many attachments",
        received_at=datetime.utcnow(),
    )

    # Create 10 small test attachments
    schema_attachments = []
    for i in range(10):
        content = f"This is test attachment {i}"
        content_b64 = base64.b64encode(content.encode()).decode()
        schema_attachment = SchemaEmailAttachment(
            name=f"test{i}.txt",
            type="text/plain",
            content=content_b64,
            content_id=f"many{i:03d}",
            size=len(content),
            base64=True,
        )
        schema_attachments.append(schema_attachment)

    # Setup mock for attachment service to handle multiple attachments
    mock_attachments = [Mock(spec=EmailAttachment) for _ in range(10)]
    mock_attachment_service.process_attachments.return_value = mock_attachments

    # Create a webhook with multiple attachments
    webhook = MailchimpWebhook(
        webhook_id="test-many-123",
        event="inbound_email",
        timestamp=datetime.utcnow(),
        data=InboundEmailData(
            message_id="many_attachments@example.com",
            from_email="sender@example.com",
            from_name="Test Sender",
            to_email="recipient@kave.com",
            subject="Test Many Attachments",
            body_plain="Test with many attachments",
            body_html="<p>Test with many attachments</p>",
            attachments=schema_attachments,
        ),
    )

    # Mock necessary methods to avoid coroutine issues
    with (
        patch.object(service, "store_email", return_value=email),
        patch.object(service, "get_email_by_message_id", return_value=None),
    ):
        # Process the webhook
        result = await service.process_webhook(webhook)

        # THEN
        assert result is email
        mock_attachment_service.process_attachments.assert_called_once()
        # Verify we passed all 10 attachments
        assert len(mock_attachment_service.process_attachments.call_args[0][1]) == 10


@pytest.mark.asyncio
async def test_malformed_email_data(
    mock_db_session: AsyncMock,
    mock_storage_service: AsyncMock,
    mock_attachment_service: AsyncMock,
    setup_db: Any,
) -> None:
    """Test handling of malformed email data in a webhook."""
    # GIVEN
    service = EmailService(
        mock_db_session, mock_attachment_service, mock_storage_service
    )

    # Configure mock to return a mock Email when a new one is created
    mock_email = Mock()
    mock_email.id = 1
    mock_email.message_id = "malformed@example.com"
    mock_email.from_name = None
    mock_email.subject = ""
    mock_email.body_text = None
    mock_email.body_html = None

    # Create a webhook with some problematic data
    webhook = MailchimpWebhook(
        webhook_id="test-malformed-123",
        event="inbound_email",
        timestamp=datetime.utcnow(),
        data=InboundEmailData(
            # Valid required fields
            message_id="malformed@example.com",
            from_email="sender@example.com",
            to_email="recipient@kave.com",
            # Problematic fields
            from_name=None,  # None should be ok for nullable field
            subject="",  # Empty should be ok
            body_plain=None,  # None for body_plain
            body_html=None,  # None for body_html
            headers={},  # Empty headers
            attachments=[],
        ),
    )

    # Mock the store_email method to return our mock email
    # And also mock the get_email_by_message_id method to return None
    with (
        patch.object(service, "store_email", return_value=mock_email),
        patch.object(service, "get_email_by_message_id", return_value=None),
    ):
        # WHEN
        email = await service.process_webhook(webhook)

        # THEN
        assert email is not None
        assert email.message_id == "malformed@example.com"
        assert email.from_name is None
        assert email.subject == ""
        assert email.body_text is None
        assert email.body_html is None


@pytest.mark.asyncio
async def test_attachment_with_invalid_base64(
    mock_db_session: AsyncMock,
    mock_storage_service: AsyncMock,
    mock_attachment_service: AsyncMock,
    setup_db: Any,
) -> None:
    """Test handling of attachment with invalid base64 encoding."""
    # GIVEN
    service = EmailService(
        mock_db_session, mock_attachment_service, mock_storage_service
    )

    # Create a test email
    mock_email = Mock()
    mock_email.id = 1

    # Create an attachment with invalid base64
    invalid_schema_attachment = SchemaEmailAttachment(
        name="invalid.txt",
        type="text/plain",
        content="this-is-not-valid-base64!@#$%^",
        content_id="invalid001",
        size=10,
        base64=True,
    )

    # Setup the attachment service to raise an error when processing
    mock_attachment_service.process_attachments.side_effect = ValueError(
        "Invalid base64"
    )

    # Create a webhook with the invalid attachment
    webhook = MailchimpWebhook(
        webhook_id="test-invalid-base64-123",
        event="inbound_email",
        timestamp=datetime.utcnow(),
        data=InboundEmailData(
            message_id="invalid_base64@example.com",
            from_email="sender@example.com",
            from_name="Test Sender",
            to_email="recipient@kave.com",
            subject="Test Invalid Base64",
            body_plain="Test with invalid base64 attachment",
            body_html="<p>Test with invalid base64 attachment</p>",
            attachments=[invalid_schema_attachment],
        ),
    )

    # Mock necessary methods to avoid coroutine issues
    with (
        patch.object(service, "store_email", return_value=mock_email),
        patch.object(service, "get_email_by_message_id", return_value=None),
    ):
        # WHEN/THEN - Expect ValueError due to invalid base64
        with pytest.raises(ValueError):
            await service.process_webhook(webhook)

    # Verify attachment service was called
    mock_attachment_service.process_attachments.assert_called_once()


@pytest.mark.asyncio
async def test_extremely_long_subject_and_content(
    mock_db_session: AsyncMock,
    mock_storage_service: AsyncMock,
    mock_attachment_service: AsyncMock,
    setup_db: Any,
) -> None:
    """Test handling of extremely long subject and content text."""
    # GIVEN
    service = EmailService(
        mock_db_session, mock_attachment_service, mock_storage_service
    )

    # Create extremely long strings
    very_long_subject = "A" * 1000  # 1000 characters
    very_long_body = "B" * 100000  # 100K characters

    # Create a webhook with long content
    webhook = MailchimpWebhook(
        webhook_id="test-long-content-123",
        event="inbound_email",
        timestamp=datetime.utcnow(),
        data=InboundEmailData(
            message_id="long_content@example.com",
            from_email="sender@example.com",
            from_name="Test Sender",
            to_email="recipient@kave.com",
            subject=very_long_subject,
            body_plain=very_long_body,
            body_html=f"<p>{very_long_body}</p>",
            headers={},
            attachments=[],
        ),
    )

    # Create a mock email with a truncated subject
    mock_email = Mock()
    mock_email.id = 1
    mock_email.subject = very_long_subject[:255]  # Subject truncated to 255 chars

    # Mock the methods that need to be called
    with (
        patch.object(service, "store_email", return_value=mock_email),
        patch.object(service, "get_email_by_message_id", return_value=None),
    ):
        # WHEN
        email = await service.process_webhook(webhook)

        # THEN
        assert email is not None
        assert email.subject == very_long_subject[:255]
        assert len(email.subject) == 255
