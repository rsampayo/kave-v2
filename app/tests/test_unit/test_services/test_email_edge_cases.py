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

from app.models.email_data import Email
from app.schemas.webhook_schemas import EmailAttachment as SchemaEmailAttachment
from app.schemas.webhook_schemas import InboundEmailData, MailchimpWebhook
from app.services.email_processing_service import EmailProcessingService
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


@pytest.mark.asyncio
async def test_process_very_large_attachment(
    mock_db_session: AsyncMock, mock_storage_service: AsyncMock, setup_db: Any
) -> None:
    """Test handling of a very large email attachment."""
    # GIVEN
    service = EmailProcessingService(mock_db_session, mock_storage_service)

    # Create a test email
    email = Email(
        message_id="large_attachment@example.com",
        from_email="sender@example.com",
        from_name="Test Sender",
        to_email="recipient@kave.com",
        subject="Test Large Attachment",
        body_text="This is a test with a large attachment",
        received_at=datetime.utcnow(),
    )
    mock_db_session.add(email)
    await mock_db_session.flush()

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

    # Convert to model attachment
    from app.services.email_processing_service import _schema_to_model_attachment

    attachment = _schema_to_model_attachment(schema_attachment)

    # Setup mock for storage service to handle the large file
    mock_storage_service.save_file.return_value = "file:///test/path/to/large.txt"

    # WHEN
    await service.process_attachments(email.id, [attachment])

    # THEN
    mock_storage_service.save_file.assert_called_once()
    # Verify the content passed to save_file matches the size of the original content
    call_args = mock_storage_service.save_file.call_args[1]
    assert len(call_args["file_data"]) == len(large_content)


@pytest.mark.asyncio
async def test_process_many_attachments(
    mock_db_session: AsyncMock, mock_storage_service: AsyncMock, setup_db: Any
) -> None:
    """Test handling of an email with many attachments."""
    # GIVEN
    service = EmailProcessingService(mock_db_session, mock_storage_service)

    # Create a test email
    email = Email(
        message_id="many_attachments@example.com",
        from_email="sender@example.com",
        from_name="Test Sender",
        to_email="recipient@kave.com",
        subject="Test Many Attachments",
        body_text="This is a test with many attachments",
        received_at=datetime.utcnow(),
    )
    mock_db_session.add(email)
    await mock_db_session.flush()

    # Create 10 small test attachments
    attachments = []
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
        from app.services.email_processing_service import _schema_to_model_attachment

        attachment = _schema_to_model_attachment(schema_attachment)
        attachments.append(attachment)

    # Setup mock for storage service to return different URIs for each file
    mock_storage_service.save_file.side_effect = [
        f"file:///test/path/to/file{i}.txt" for i in range(10)
    ]

    # WHEN
    await service.process_attachments(email.id, attachments)

    # THEN
    assert mock_storage_service.save_file.call_count == 10


@pytest.mark.asyncio
async def test_malformed_email_data(
    mock_db_session: AsyncMock, mock_storage_service: AsyncMock, setup_db: Any
) -> None:
    """Test handling of malformed email data in a webhook."""
    # GIVEN
    service = EmailProcessingService(mock_db_session, mock_storage_service)

    # Configure mocks for email check
    mock_email_result = AsyncMock()
    mock_email_result.scalar_one_or_none.return_value = None
    mock_db_session.execute.return_value = mock_email_result

    # Configure mock to return a mock Email when a new one is created
    mock_email = Mock()
    mock_email.id = 1
    mock_email.message_id = "malformed@example.com"
    mock_email.from_name = None
    mock_email.subject = ""
    mock_email.body_text = None
    mock_email.body_html = None
    mock_db_session.flush.return_value = None
    mock_db_session.commit.return_value = None

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
    with patch.object(service, "store_email", return_value=mock_email):
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
    mock_db_session: AsyncMock, mock_storage_service: AsyncMock, setup_db: Any
) -> None:
    """Test handling of attachment with invalid base64 encoding."""
    # GIVEN
    # Create a completely non-async mock setup to avoid warnings
    db_mock = MagicMock(spec=AsyncSession)
    storage_mock = MagicMock(spec=StorageService)

    # Only mock methods that need to be awaited as AsyncMock
    storage_mock.save_file = AsyncMock(side_effect=ValueError("Invalid base64"))

    service = EmailProcessingService(db_mock, storage_mock)

    # Create a test email
    email = Email(
        id=1,
        message_id="invalid_attachment@example.com",
        from_email="sender@example.com",
        from_name="Test Sender",
        to_email="recipient@kave.com",
        subject="Test Invalid Attachment",
        body_text="This is a test with an invalid attachment",
        received_at=datetime.utcnow(),
    )

    # Create an attachment with invalid base64
    invalid_schema_attachment = SchemaEmailAttachment(
        name="invalid.txt",
        type="text/plain",
        content="this-is-not-valid-base64!@#$%^",
        content_id="invalid001",
        size=10,
        base64=True,
    )

    from app.services.email_processing_service import _schema_to_model_attachment

    attachment = _schema_to_model_attachment(invalid_schema_attachment)

    # WHEN/THEN
    with pytest.raises(ValueError):  # Base64 decoding should raise ValueError
        await service.process_attachments(email.id, [attachment])


@pytest.mark.asyncio
async def test_extremely_long_subject_and_content(
    mock_db_session: AsyncMock, mock_storage_service: AsyncMock, setup_db: Any
) -> None:
    """Test handling of an email with extremely long subject and content."""
    # GIVEN
    service = EmailProcessingService(mock_db_session, mock_storage_service)

    # Configure mocks for email check
    mock_email_result = AsyncMock()
    mock_email_result.scalar_one_or_none.return_value = None
    mock_db_session.execute.return_value = mock_email_result

    # Mock Email object
    mock_email = Mock()
    mock_email.id = 1
    mock_email.message_id = "long_content@example.com"
    mock_email.subject = "A" * 255  # Truncated to 255 chars
    mock_email.body_text = "B" * 100_000
    mock_email.body_html = "<p>" + ("C" * 100_000) + "</p>"
    mock_db_session.flush.return_value = None
    mock_db_session.commit.return_value = None

    # Create a test webhook with extremely long subject and content
    long_subject = "A" * 1000  # 1000 characters
    long_plain_body = "B" * 100_000  # 100K characters
    long_html_body = "<p>" + ("C" * 100_000) + "</p>"  # 100K+ characters

    webhook = MailchimpWebhook(
        webhook_id="test-long-123",
        event="inbound_email",
        timestamp=datetime.utcnow(),
        data=InboundEmailData(
            message_id="long_content@example.com",
            from_email="sender@example.com",
            from_name="Test Sender",
            to_email="recipient@kave.com",
            subject=long_subject,
            body_plain=long_plain_body,
            body_html=long_html_body,
            headers={},
            attachments=[],
        ),
    )

    # Mock the store_email method to return our mock email
    with patch.object(service, "store_email", return_value=mock_email):
        # WHEN
        email = await service.process_webhook(webhook)

        # THEN
        assert email is not None
        # Subject should be truncated to 255 characters
        assert len(email.subject) == 255
        assert email.subject == "A" * 255
        # Body content should be stored as-is
        assert email.body_text is not None
        assert len(email.body_text) == 100_000
        assert email.body_html is not None
        assert len(email.body_html) > 100_000
