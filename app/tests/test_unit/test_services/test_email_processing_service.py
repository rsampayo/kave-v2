"""Unit tests for EmailProcessingService."""

import base64
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.email_data import Attachment, Email, EmailAttachment
from app.schemas.webhook_schemas import EmailAttachment as SchemaEmailAttachment
from app.schemas.webhook_schemas import InboundEmailData, MailchimpWebhook
from app.services.email_processing_service import (
    EmailProcessingService,
    get_email_service,
)
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
    )


@pytest.fixture
def mock_storage_service() -> AsyncMock:
    """Create a mock storage service for tests."""
    mock = AsyncMock(spec=StorageService)
    mock.save_file.return_value = "file:///test/path/to/file.txt"
    return mock


@pytest.mark.asyncio
async def test_get_email_service() -> None:
    """Test that get_email_service returns a proper EmailProcessingService instance."""
    # Mock database session and storage service
    mock_db = MagicMock(spec=AsyncSession)
    mock_storage = MagicMock(spec=StorageService)

    # Get service from dependency function
    service = await get_email_service(mock_db, mock_storage)

    # Verify service was created with the right DB session and storage
    assert isinstance(service, EmailProcessingService)
    assert service.db == mock_db
    assert service.storage == mock_storage


@pytest.mark.asyncio
async def test_store_email(
    db_session: AsyncSession, mock_storage_service: AsyncMock, setup_db: Any
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

    service = EmailProcessingService(session_mock, mock_storage_service)
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
async def test_process_attachments(
    db_session: AsyncSession, mock_storage_service: AsyncMock, setup_db: Any
) -> None:
    """Test processing of email attachments."""
    # GIVEN
    service = EmailProcessingService(db_session, mock_storage_service)

    # Create a test email
    email = Email(
        message_id="test@example.com",
        from_email="sender@example.com",
        from_name="Test Sender",
        to_email="recipient@kave.com",
        subject="Test Email",
        body_text="This is a test email",
        received_at=datetime.utcnow(),
    )
    db_session.add(email)
    await db_session.flush()

    # Test attachment data
    test_content = "This is a test attachment"
    test_content_b64 = base64.b64encode(test_content.encode()).decode()

    # First create schema attachments
    schema_attachments = [
        SchemaEmailAttachment(
            name="test.txt",
            type="text/plain",
            content=test_content_b64,
            content_id="att001",
            size=len(test_content),
        )
    ]

    # Convert to model attachments
    attachments = [schema_to_model_attachment(a) for a in schema_attachments]

    # Setup mock for storage service
    expected_storage_uri = f"file:///test/attachments/{email.id}/test.txt"
    mock_storage_service.save_file.return_value = expected_storage_uri

    # WHEN
    result = await service.process_attachments(email.id, attachments)

    # Explicitly commit to make sure the attachment is saved
    await db_session.commit()

    # THEN
    assert len(result) == 1
    assert result[0].filename == "test.txt"
    assert result[0].content_type == "text/plain"
    assert result[0].content_id == "att001"
    assert result[0].size == len(test_content)
    assert result[0].storage_uri == expected_storage_uri

    # Verify an attachment was added to the database
    query = select(Attachment).where(Attachment.email_id == email.id)
    db_result = await db_session.execute(query)
    attachment_records = db_result.scalars().all()
    assert len(attachment_records) == 1
    assert attachment_records[0].filename == "test.txt"
    assert attachment_records[0].storage_uri == expected_storage_uri

    # Verify storage service was called correctly
    mock_storage_service.save_file.assert_called_once()
    call_args = mock_storage_service.save_file.call_args[1]
    assert call_args["content_type"] == "text/plain"
    assert isinstance(call_args["file_data"], bytes)
    assert "attachments/" in call_args["object_key"]
    assert "test.txt" in call_args["object_key"]


@pytest.mark.asyncio
async def test_process_attachments_file_write_error(
    db_session: AsyncSession, mock_storage_service: AsyncMock, setup_db: Any
) -> None:
    """Test handling of file write errors during attachment processing."""
    # GIVEN
    # Create a non-async mock db to avoid "coroutine was never awaited" warnings
    non_async_db = MagicMock(spec=AsyncSession)
    non_async_db.add = MagicMock()

    # Configure async mocks to have return_value=None
    non_async_db.execute = AsyncMock(return_value=MagicMock())
    non_async_db.flush = AsyncMock(return_value=None)
    non_async_db.commit = AsyncMock(return_value=None)
    non_async_db.rollback = AsyncMock(return_value=None)

    service = EmailProcessingService(non_async_db, mock_storage_service)

    # Create a test email
    email = Email(
        message_id="file_error@example.com",
        from_email="sender@example.com",
        from_name="Test Sender",
        to_email="recipient@kave.com",
        subject="Test File Error",
        body_text="This is a test for file writing errors",
        received_at=datetime.utcnow(),
    )
    non_async_db.add(email)
    await non_async_db.flush()

    # Test attachment data
    test_content = "Test content for file error"
    test_content_b64 = base64.b64encode(test_content.encode()).decode()

    # Create schema attachment
    schema_attachment = SchemaEmailAttachment(
        name="error.txt",
        type="text/plain",
        content=test_content_b64,
        content_id="error001",
        size=len(test_content),
    )

    # Convert to model attachment
    attachments = [schema_to_model_attachment(schema_attachment)]

    # Make storage service raise an error
    mock_storage_service.save_file.side_effect = PermissionError("Permission denied")

    # WHEN/THEN - Ensure the error is propagated
    with pytest.raises(PermissionError, match="Permission denied"):
        await service.process_attachments(email.id, attachments)

    # Verify attachment record was not created
    query = select(Attachment).where(Attachment.email_id == email.id)
    # Set up a result that returns empty list
    result_mock = MagicMock()
    result_mock.scalars = MagicMock(return_value=MagicMock())
    result_mock.scalars().all = MagicMock(return_value=[])
    non_async_db.execute.return_value = result_mock

    result = await non_async_db.execute(query)
    attachments_db = result.scalars().all()
    assert len(attachments_db) == 0


@pytest.mark.asyncio
async def test_process_webhook_basic(
    db_session: AsyncSession, mock_storage_service: AsyncMock, setup_db: Any
) -> None:
    """Test processing a basic webhook with no attachments."""
    # GIVEN
    service = EmailProcessingService(db_session, mock_storage_service)

    # Create a test webhook
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
    assert email.body_text == webhook.data.body_plain
    assert email.body_html == webhook.data.body_html

    # Check it was saved to the database
    query = select(Email).where(Email.message_id == webhook.data.message_id)
    result = await db_session.execute(query)
    db_email = result.scalar_one_or_none()
    assert db_email is not None
    assert db_email.id == email.id


@pytest.mark.asyncio
async def test_process_webhook_with_attachments(
    db_session: AsyncSession, mock_storage_service: AsyncMock, setup_db: Any
) -> None:
    """Test processing a webhook with attachments."""
    # Arrange
    service = EmailProcessingService(db_session, mock_storage_service)
    webhook = create_test_webhook()

    # Add an attachment to the webhook
    schema_attachment = SchemaEmailAttachment(
        name="test.txt",
        type="text/plain",
        content=base64.b64encode(b"Test content").decode(),
        content_id="123",
        size=123,
    )
    webhook.data.attachments.append(schema_attachment)

    # Setup mock for storage service
    mock_storage_service.save_file.return_value = "file:///test/attachments/test.txt"

    # Act
    email = await service.process_webhook(webhook)

    # Assert
    assert email is not None
    assert email.message_id == webhook.data.message_id

    # Check for attachment in database
    query = select(Attachment).where(Attachment.email_id == email.id)
    result = await db_session.execute(query)
    attachments = result.scalars().all()
    assert len(attachments) == 1
    assert attachments[0].filename == "test.txt"
    assert attachments[0].content_type == "text/plain"
    assert attachments[0].storage_uri == "file:///test/attachments/test.txt"

    # Verify storage service was called
    mock_storage_service.save_file.assert_called_once()


@pytest.mark.asyncio
async def test_process_webhook_error_handling(
    db_session: AsyncSession, mock_storage_service: AsyncMock, setup_db: Any
) -> None:
    """Test error handling during webhook processing."""
    # GIVEN
    service = EmailProcessingService(db_session, mock_storage_service)

    # Create a proper mock session to avoid coroutine warnings
    session_mock = AsyncMock(spec=AsyncSession)
    service.db = session_mock  # Replace the session with our mock

    # Create a test webhook with an error that will occur during processing
    webhook = create_test_webhook()

    # Make the execute method raise an exception
    error_message = "Database error during processing"
    session_mock.execute.side_effect = RuntimeError(error_message)

    # WHEN/THEN
    with pytest.raises(ValueError, match=f"Email processing failed: {error_message}"):
        await service.process_webhook(webhook)

    # Verify session commit was not called but rollback was
    session_mock.commit.assert_not_awaited()
    session_mock.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_duplicate_email_handling(
    db_session: AsyncSession, mock_storage_service: AsyncMock, setup_db: Any
) -> None:
    """Test handling of duplicate emails."""
    # GIVEN
    service = EmailProcessingService(db_session, mock_storage_service)
    webhook = create_test_webhook()

    # First store the email
    email1 = await service.process_webhook(webhook)
    await db_session.commit()

    # WHEN - Process the exact same webhook again
    email2 = await service.process_webhook(webhook)

    # THEN - Should get back the same email (not create a duplicate)
    assert email1.id == email2.id
    assert email1.message_id == email2.message_id

    # Verify only one email with this message_id exists in the database
    from sqlalchemy import func

    count_query = (
        select(func.count())
        .select_from(Email)
        .where(Email.message_id == webhook.data.message_id)
    )
    result = await db_session.execute(count_query)
    count = result.scalar_one()
    assert count == 1


@pytest.mark.asyncio
async def test_get_email_by_message_id(
    db_session: AsyncSession, mock_storage_service: AsyncMock, setup_db: Any
) -> None:
    """Test retrieval of an email by its message ID."""
    # GIVEN
    service = EmailProcessingService(db_session, mock_storage_service)
    message_id = "test_retrieval@example.com"

    # Create a test email in the database
    email = Email(
        message_id=message_id,
        from_email="sender@example.com",
        from_name="Test Sender",
        to_email="recipient@kave.com",
        subject="Test Retrieval",
        body_text="This is a test for retrieval by message ID",
        received_at=datetime.utcnow(),
    )
    db_session.add(email)
    await db_session.commit()

    # WHEN - Get the email by message ID
    result = await service.get_email_by_message_id(message_id)

    # THEN - Should retrieve the correct email
    assert result is not None
    assert result.message_id == message_id
    assert result.from_email == "sender@example.com"
    assert result.subject == "Test Retrieval"

    # Try with a non-existent message ID
    result = await service.get_email_by_message_id("nonexistent@example.com")
    assert result is None


@pytest.mark.asyncio
async def test_process_attachments_corrects_pdf_content_type(
    db_session: AsyncSession, mock_storage_service: AsyncMock, setup_db: Any
) -> None:
    """Test that PDF files with wrong content type get application/pdf content type."""
    # Create the service
    service = EmailProcessingService(db_session, mock_storage_service)

    # Test data - a PDF file with application/octet-stream content type
    email_id = 123
    attachments = [
        EmailAttachment(
            name="document.pdf",
            type="application/octet-stream",  # Wrong content type
            content="SGVsbG8gV29ybGQ=",  # Base64 encoded "Hello World"
            content_id="123",
            size=100,
            base64=True,
        ),
        EmailAttachment(
            name="another.PDF",  # Upper case extension
            type="binary/octet-stream",  # Another incorrect type
            content="SGVsbG8gV29ybGQ=",
            content_id="456",
            size=100,
            base64=True,
        ),
        EmailAttachment(
            name="normal.txt",  # Not a PDF
            type="text/plain",
            content="SGVsbG8gV29ybGQ=",
            content_id="789",
            size=100,
            base64=True,
        ),
    ]

    # Configure mock storage service
    mock_storage_service.save_file.return_value = "s3://bucket/path"

    # Process attachments
    result = await service.process_attachments(email_id, attachments)

    # Verify content types were corrected
    assert len(result) == 3
    assert result[0].content_type == "application/pdf"
    assert result[1].content_type == "application/pdf"
    assert result[2].content_type == "text/plain"  # This one should remain unchanged

    # Verify storage service was called with correct content types
    assert mock_storage_service.save_file.call_count == 3
    call_args_list = mock_storage_service.save_file.call_args_list

    # Extract the content_type from each call
    pdf1_call = call_args_list[0].kwargs
    pdf2_call = call_args_list[1].kwargs
    txt_call = call_args_list[2].kwargs

    assert pdf1_call["content_type"] == "application/pdf"
    assert pdf2_call["content_type"] == "application/pdf"
    assert txt_call["content_type"] == "text/plain"

    # Check object keys contain corrected filenames
    assert "document.pdf" in pdf1_call["object_key"]
    assert "another.PDF" in pdf2_call["object_key"]  # Should preserve case
    assert "normal.txt" in txt_call["object_key"]
