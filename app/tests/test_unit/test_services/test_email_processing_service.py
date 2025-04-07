"""Unit tests for the email processing service."""

import base64
import os
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

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


@pytest.mark.asyncio
async def test_get_email_service() -> None:
    """Test that get_email_service returns a proper EmailProcessingService instance."""
    # Mock database session
    mock_db = AsyncMock(spec=AsyncSession)

    # Get service from dependency function
    service = await get_email_service(mock_db)

    # Verify service was created with the right DB session
    assert isinstance(service, EmailProcessingService)
    assert service.db == mock_db


@pytest.mark.asyncio
async def test_store_email(db_session: AsyncSession, setup_db: Any) -> None:
    """Test storing an email in the database."""
    # GIVEN
    service = EmailProcessingService(db_session)
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

    # Verify it was added to the database
    result = await db_session.execute(
        select(Email).where(Email.message_id == "test123@example.com")
    )
    db_email = result.scalar_one_or_none()
    assert db_email is not None
    assert db_email.id == email.id


@pytest.mark.asyncio
async def test_process_attachments(db_session: AsyncSession, setup_db: Any) -> None:
    """Test processing of email attachments."""
    # GIVEN
    service = EmailProcessingService(db_session)

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

    # Create a test directory
    test_attachments_dir = Path(os.path.dirname(__file__)) / "test_attachments"
    test_attachments_dir.mkdir(exist_ok=True, parents=True)

    # Run the real function but with a patch to redirect the file writes
    with patch(
        "app.services.email_processing_service.ATTACHMENTS_DIR", test_attachments_dir
    ):
        # When using the real function, we need to handle the database commit
        try:
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

            # Verify an attachment was added to the database
            query = select(Attachment).where(Attachment.email_id == email.id)
            db_result = await db_session.execute(query)
            attachment_records = db_result.scalars().all()
            assert len(attachment_records) == 1
            assert attachment_records[0].filename == "test.txt"

            # Verify file was created - use the file_path from the database record
            assert attachment_records[0].file_path is not None
            file_path = Path(attachment_records[0].file_path)
            assert file_path.exists()

        finally:
            # Clean up after the test
            import shutil

            if test_attachments_dir.exists():
                shutil.rmtree(test_attachments_dir)


@pytest.mark.asyncio
async def test_process_attachments_file_write_error(
    db_session: AsyncSession, setup_db: Any
) -> None:
    """Test handling of file write errors during attachment processing."""
    # GIVEN
    service = EmailProcessingService(db_session)

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
    db_session.add(email)
    await db_session.flush()

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

    # Mock the file open operation to raise an error
    test_attachments_dir = Path(os.path.dirname(__file__)) / "test_error_attachments"
    test_attachments_dir.mkdir(exist_ok=True, parents=True)

    try:
        with (
            patch(
                "app.services.email_processing_service.ATTACHMENTS_DIR",
                test_attachments_dir,
            ),
            patch("builtins.open", side_effect=PermissionError("Permission denied")),
        ):
            # WHEN/THEN - Ensure the error is propagated
            with pytest.raises(PermissionError, match="Permission denied"):
                await service.process_attachments(email.id, attachments)

            # Verify attachment record was not created
            query = select(Attachment).where(Attachment.email_id == email.id)
            result = await db_session.execute(query)
            attachments_db = result.scalars().all()
            assert len(attachments_db) == 0

    finally:
        # Clean up
        import shutil

        if test_attachments_dir.exists():
            shutil.rmtree(test_attachments_dir)


@pytest.mark.asyncio
async def test_process_webhook_basic(db_session: AsyncSession, setup_db: Any) -> None:
    """Test processing a basic webhook with no attachments."""
    # Arrange
    service = EmailProcessingService(db_session)
    webhook = create_test_webhook()

    # Act
    email = await service.process_webhook(webhook)

    # Assert
    assert email is not None
    assert email.message_id == webhook.data.message_id
    assert email.subject == webhook.data.subject
    assert email.from_email == webhook.data.from_email
    assert email.to_email == webhook.data.to_email
    assert email.webhook_id == webhook.webhook_id
    assert email.webhook_event == webhook.event

    # Verify it's in the database
    query = select(Email).where(Email.message_id == webhook.data.message_id)
    result = await db_session.execute(query)
    saved_email = result.scalar_one_or_none()
    assert saved_email is not None
    assert saved_email.id == email.id


@pytest.mark.asyncio
async def test_process_webhook_with_attachments(
    db_session: AsyncSession, setup_db: Any
) -> None:
    """Test processing a webhook with attachments."""
    # Arrange
    service = EmailProcessingService(db_session)
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

    # Create a Path object for test attachments directory
    test_attachments_dir = Path(os.path.dirname(__file__)) / "test_webhook_attachments"
    test_attachments_dir.mkdir(exist_ok=True, parents=True)

    try:
        # Run the real function but with a patch to redirect the file writes
        with patch(
            "app.services.email_processing_service.ATTACHMENTS_DIR",
            test_attachments_dir,
        ):
            # Act
            email = await service.process_webhook(webhook)

        # Assert
        assert email is not None

        # Query for the attachments separately to avoid lazy-loading issues
        query = select(Attachment).where(Attachment.email_id == email.id)
        result = await db_session.execute(query)
        attachments = result.scalars().all()

        assert len(attachments) == 1
        assert attachments[0].filename == "test.txt"
        assert attachments[0].content_type == "text/plain"
        assert attachments[0].size == 123

        # Verify file was created - use the file_path from the database record
        assert attachments[0].file_path is not None
        file_path = Path(attachments[0].file_path)
        assert file_path.exists()

    finally:
        # Clean up after the test
        import shutil

        if test_attachments_dir.exists():
            shutil.rmtree(test_attachments_dir)


@pytest.mark.asyncio
async def test_process_webhook_error_handling() -> None:
    """Test error handling in process_webhook when something fails."""
    # Mock the necessary objects
    mock_db = AsyncMock(spec=AsyncSession)
    service = EmailProcessingService(mock_db)
    webhook = create_test_webhook()

    # Make store_email raise an exception
    mock_error = ValueError("Test error")
    with patch.object(service, "store_email", side_effect=mock_error):
        # Test the error handling
        with pytest.raises(ValueError, match="Email processing failed:.*Test error"):
            await service.process_webhook(webhook)

        # Verify rollback was called
        mock_db.rollback.assert_called_once()


@pytest.mark.asyncio
async def test_duplicate_email_handling(
    db_session: AsyncSession, setup_db: Any
) -> None:
    """Test handling of duplicate emails."""
    # Arrange
    service = EmailProcessingService(db_session)
    webhook = create_test_webhook()

    # Act - process the same webhook twice
    email1 = await service.process_webhook(webhook)
    email2 = await service.process_webhook(webhook)

    # Assert
    assert email1.id == email2.id
    assert email1.message_id == email2.message_id

    # Check we only have one record in the database
    query = select(Email).where(Email.message_id == webhook.data.message_id)
    result = await db_session.execute(query)
    emails = result.scalars().all()
    assert len(emails) == 1


@pytest.mark.asyncio
async def test_get_email_by_message_id(db_session: AsyncSession, setup_db: Any) -> None:
    """Test retrieval of an email by its message ID."""
    # GIVEN
    service = EmailProcessingService(db_session)

    # Create a test email
    test_email = Email(
        message_id="test_retrieval@example.com",
        from_email="sender@example.com",
        from_name="Test Sender",
        to_email="recipient@kave.com",
        subject="Test Retrieval",
        body_text="This is a test email for retrieval",
        received_at=datetime.utcnow(),
    )
    db_session.add(test_email)
    await db_session.flush()

    # WHEN - test retrieving existing email
    result = await service.get_email_by_message_id("test_retrieval@example.com")

    # THEN
    assert result is not None
    assert result.message_id == "test_retrieval@example.com"
    assert result.from_email == "sender@example.com"

    # WHEN - test retrieving non-existent email
    non_existent = await service.get_email_by_message_id("nonexistent@example.com")

    # THEN
    assert non_existent is None
