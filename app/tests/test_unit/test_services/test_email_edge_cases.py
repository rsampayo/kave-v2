"""Tests for email processing edge cases.

This module tests handling of unusual, extreme, or edge cases in email processing,
including large attachments, malformed data, etc.
"""

import base64
import os
from datetime import datetime
from pathlib import Path
from typing import Any, List
from unittest.mock import MagicMock, mock_open, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.email_data import Attachment, Email, EmailAttachment
from app.schemas.webhook_schemas import InboundEmailData, MailchimpWebhook
from app.services.email_processing_service import EmailProcessingService


@pytest.mark.asyncio
async def test_process_very_large_attachment(
    db_session: AsyncSession, setup_db: Any
) -> None:
    """Test handling of a very large email attachment."""
    # GIVEN
    service = EmailProcessingService(db_session)

    # Create a test email
    email = Email(
        message_id="large_attachment@example.com",
        from_email="sender@example.com",
        from_name="Test Sender",
        to_email="receiver@kave.com",
        subject="Test Email with Large Attachment",
        body_text="This email has a large attachment",
        received_at=datetime.utcnow(),
    )
    db_session.add(email)
    await db_session.flush()

    # Create a large in-memory attachment (10 MB of repeating text)
    large_size = 10 * 1024 * 1024  # 10 MB
    large_content = "X" * large_size
    content_b64 = base64.b64encode(large_content.encode()).decode()

    # Create a schema-compatible attachment
    from app.schemas.webhook_schemas import EmailAttachment as SchemaEmailAttachment

    schema_attachment = SchemaEmailAttachment(
        name="large_file.txt",
        type="text/plain",
        content=content_b64,
        content_id="large001",
        size=large_size,
    )

    # Convert to model attachment for the service
    attachments = [
        EmailAttachment(
            name=schema_attachment.name,
            type=schema_attachment.type,
            content=schema_attachment.content or "",
            content_id=schema_attachment.content_id,
            size=schema_attachment.size,
        )
    ]

    # Create test directory
    test_attachments_dir = Path(os.path.dirname(__file__)) / "test_attachments"
    test_attachments_dir.mkdir(exist_ok=True)

    # Mock the file operations to avoid actually writing a large file
    with (
        patch(
            "app.services.email_processing_service.ATTACHMENTS_DIR",
            test_attachments_dir,
        ),
        patch("builtins.open") as mock_open_obj,
    ):
        mock_file = MagicMock()
        mock_open_obj.return_value.__enter__.return_value = mock_file

        try:
            # WHEN
            result = await service.process_attachments(email.id, attachments)
            await db_session.commit()

            # THEN
            assert len(result) == 1
            assert result[0].filename == "large_file.txt"
            assert result[0].size == large_size

            # Verify the write operation was called with the correct data
            mock_file.write.assert_called_once()

        finally:
            # Clean up
            import shutil

            if test_attachments_dir.exists():
                shutil.rmtree(test_attachments_dir)


@pytest.mark.asyncio
async def test_process_many_attachments(
    db_session: AsyncSession, setup_db: Any
) -> None:
    """Test handling of an email with many attachments."""
    # GIVEN
    service = EmailProcessingService(db_session)

    # Create a test email
    email = Email(
        message_id="many_attachments@example.com",
        from_email="sender@example.com",
        from_name="Test Sender",
        to_email="receiver@kave.com",
        subject="Test Email with Many Attachments",
        body_text="This email has many attachments",
        received_at=datetime.utcnow(),
    )
    db_session.add(email)
    await db_session.flush()

    # Create multiple attachments (20)
    num_attachments = 20
    from app.schemas.webhook_schemas import EmailAttachment as SchemaEmailAttachment

    schema_attachments: List[SchemaEmailAttachment] = []

    for i in range(num_attachments):
        content = f"Attachment {i} content"
        content_b64 = base64.b64encode(content.encode()).decode()

        schema_attachments.append(
            SchemaEmailAttachment(
                name=f"attachment{i}.txt",
                type="text/plain",
                content=content_b64,
                content_id=f"att{i:03d}",
                size=len(content),
            )
        )

    # Convert to model attachments for the service
    model_attachments = [
        EmailAttachment(
            name=attachment.name,
            type=attachment.type,
            content=attachment.content or "",
            content_id=attachment.content_id,
            size=attachment.size,
        )
        for attachment in schema_attachments
    ]

    # Create test directory
    test_attachments_dir = Path(os.path.dirname(__file__)) / "test_many_attachments"
    test_attachments_dir.mkdir(exist_ok=True, parents=True)

    # Mock file operations
    with (
        patch(
            "app.services.email_processing_service.ATTACHMENTS_DIR",
            test_attachments_dir,
        ),
        patch("builtins.open", mock_open()),
    ):
        try:
            # WHEN
            result = await service.process_attachments(email.id, model_attachments)
            await db_session.commit()

            # THEN
            assert len(result) == num_attachments

            # Verify database records
            query = select(Attachment).where(Attachment.email_id == email.id)
            db_result = await db_session.execute(query)
            db_attachments = db_result.scalars().all()
            assert len(db_attachments) == num_attachments

        finally:
            # Clean up
            import shutil

            if test_attachments_dir.exists():
                shutil.rmtree(test_attachments_dir)


@pytest.mark.asyncio
async def test_malformed_email_data(db_session: AsyncSession, setup_db: Any) -> None:
    """Test handling of malformed email data in a webhook."""
    # GIVEN
    service = EmailProcessingService(db_session)

    # Create a webhook with malformed email data but with valid email addresses
    malformed_inbound_data = InboundEmailData(
        # Use valid but unusual values for required fields
        message_id="malformed-id@example.com",
        from_email="malformed@example.com",  # Valid email required
        from_name="   ",  # Empty name but not None
        to_email="recipient@kave.com",
        subject="   ",  # Empty subject but not None
        body_plain="",  # Empty body
        body_html="",  # Empty HTML
        headers={},
        attachments=[],
    )

    malformed_webhook = MailchimpWebhook(
        webhook_id="malformed_webhook_123",
        event="inbound_email",
        timestamp=datetime.utcnow(),
        data=malformed_inbound_data,
    )

    # WHEN
    email = await service.process_webhook(malformed_webhook)

    # THEN - The service should handle the unusual fields gracefully
    assert email is not None
    assert email.message_id == "malformed-id@example.com"
    assert email.from_email == "malformed@example.com"
    assert email.from_name == "   "
    assert email.subject == "   "

    # Verify it's in the database
    query = select(Email).where(Email.webhook_id == malformed_webhook.webhook_id)
    result = await db_session.execute(query)
    saved_email = result.scalar_one_or_none()
    assert saved_email is not None


@pytest.mark.asyncio
async def test_attachment_with_invalid_base64(
    db_session: AsyncSession, setup_db: Any
) -> None:
    """Test handling of attachment with invalid base64 encoding."""
    # GIVEN
    service = EmailProcessingService(db_session)

    # Create a test email
    email = Email(
        message_id="invalid_base64@example.com",
        from_email="sender@example.com",
        from_name="Test Sender",
        to_email="receiver@kave.com",
        subject="Test Email with Invalid Attachment",
        body_text="This email has an invalid attachment",
        received_at=datetime.utcnow(),
    )
    db_session.add(email)
    await db_session.flush()

    # Create a schema-compatible attachment with invalid base64
    from app.schemas.webhook_schemas import EmailAttachment as SchemaEmailAttachment

    schema_attachment = SchemaEmailAttachment(
        name="invalid.txt",
        type="text/plain",
        content="This===is+++not/valid/base64!@#$%^&*",  # Really invalid base64
        content_id="invalid001",
        size=100,
    )

    # Convert to model attachment
    attachments = [
        EmailAttachment(
            name=schema_attachment.name,
            type=schema_attachment.type,
            content=schema_attachment.content or "",
            content_id=schema_attachment.content_id,
            size=schema_attachment.size,
        )
    ]

    # Create test directory
    test_attachments_dir = Path(os.path.dirname(__file__)) / "test_invalid_attachments"
    test_attachments_dir.mkdir(exist_ok=True, parents=True)

    try:
        with patch(
            "app.services.email_processing_service.ATTACHMENTS_DIR",
            test_attachments_dir,
        ):
            # WHEN/THEN - Should raise a binascii error due to invalid base64
            with pytest.raises((ValueError, Exception)):  # Accept any exception type
                await service.process_attachments(email.id, attachments)

            # Verify no attachment record was created
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
async def test_extremely_long_subject_and_content(
    db_session: AsyncSession, setup_db: Any
) -> None:
    """Test handling of an email with extremely long subject and content."""
    # GIVEN
    service = EmailProcessingService(db_session)

    # Create extremely long subject (1000 characters) and body (100,000 characters)
    long_subject = "A" * 1000
    long_body = "B" * 100000

    # Create a schema-compatible email data
    inbound_data = InboundEmailData(
        message_id="long_content@example.com",
        from_email="sender@example.com",
        from_name="Test Sender",
        to_email="recipient@kave.com",
        subject=long_subject,
        body_plain=long_body,
        body_html=f"<html><body><p>{long_body}</p></body></html>",
        headers={},
        attachments=[],
    )

    webhook = MailchimpWebhook(
        webhook_id="long_content_webhook_123",
        event="inbound_email",
        timestamp=datetime.utcnow(),
        data=inbound_data,
    )

    # WHEN
    email = await service.process_webhook(webhook)

    # THEN - The service should handle the long content
    assert email is not None
    # Subject should be truncated to 255 chars (database column limit)
    assert len(email.subject) <= 255
    # Body text should be stored complete
    assert email.body_text is not None
    assert len(email.body_text) == len(long_body)

    # Verify database record
    query = select(Email).where(Email.message_id == "long_content@example.com")
    result = await db_session.execute(query)
    db_email = result.scalar_one_or_none()
    assert db_email is not None
    assert len(db_email.subject) <= 255  # Subject truncated in DB
    assert db_email.body_text is not None
    assert len(db_email.body_text) == len(long_body)  # Body stored complete
