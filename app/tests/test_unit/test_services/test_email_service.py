"""Module providing Test Email Service functionality for the tests test unit test services."""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.email_data import Email
from app.schemas.webhook_schemas import (
    EmailAttachment,
    InboundEmailData,
    MailchimpWebhook,
)
from app.services.attachment_service import AttachmentService
from app.services.email_service import EmailService
from app.services.storage_service import StorageService


@pytest.fixture
def mock_storage_service() -> AsyncMock:
    """Create a mock storage service."""
    service = AsyncMock(spec=StorageService)
    service.save_file.return_value = "s3://test-bucket/test.txt"
    service.get_file.return_value = b"test content"
    return service


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Create a mock db session."""
    session = AsyncMock(spec=AsyncSession)
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()

    # Create a mock for execute that properly returns scalar_one_or_none
    execute_result = AsyncMock()
    execute_result.scalar_one_or_none = MagicMock()

    # Make execute return the execute_result when awaited
    session.execute = AsyncMock(return_value=execute_result)
    return session


@pytest.fixture
def mock_attachment_service() -> AsyncMock:
    """Create a mock attachment service."""
    service = AsyncMock(spec=AttachmentService)
    # Configure process_attachments to return an empty list when awaited
    service.process_attachments.return_value = []
    return service


@pytest.fixture
def sample_email() -> Email:
    """Create a sample email model."""
    return Email(
        id=1,
        message_id="<test@example.com>",
        from_email="sender@example.com",
        to_email="recipient@example.com",
        subject="Test Subject",
        body_text="Test body",
        body_html="<p>Test body</p>",
        webhook_id="test-webhook",
        webhook_event="inbound_email",
        received_at=datetime.utcnow(),
    )


@pytest.fixture
def sample_email_data() -> InboundEmailData:
    """Create sample email data."""
    return InboundEmailData(
        message_id=f"<{uuid.uuid4()}@example.com>",
        from_email="sender@example.com",
        from_name="Sender Name",
        to_email="recipient@example.com",
        subject="Test Subject",
        body_plain="Test content",
        body_html="<p>Test content</p>",
        headers={"From": "sender@example.com"},
        attachments=[],
    )


@pytest.fixture
def sample_webhook(sample_email_data: InboundEmailData) -> MailchimpWebhook:
    """Create a sample webhook with email data."""
    return MailchimpWebhook(
        webhook_id=str(uuid.uuid4()),
        event="inbound_email",
        timestamp=datetime.utcnow(),
        data=sample_email_data,
    )


class TestEmailService:
    """Test suite for the EmailService."""

    @pytest.mark.asyncio
    async def test_store_email(
        self,
        mock_db_session: AsyncMock,
        mock_attachment_service: AsyncMock,
        mock_storage_service: AsyncMock,
        sample_email_data: InboundEmailData,
        sample_email: Email,
    ) -> None:
        """Test storing an email."""
        # Arrange
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = None

        service = EmailService(
            db=mock_db_session,
            attachment_service=mock_attachment_service,
            storage=mock_storage_service,
        )

        webhook_id = "test-webhook-id"
        event = "inbound_email"

        # Mock get_email_by_message_id to return None (email doesn't exist)
        # Create a new Email with the expected webhook_id for this specific test
        test_email = Email(
            id=1,
            message_id=sample_email_data.message_id,
            from_email=sample_email_data.from_email,
            to_email=sample_email_data.to_email,
            subject=sample_email_data.subject,
            body_text=sample_email_data.body_plain,
            body_html=sample_email_data.body_html,
            webhook_id=webhook_id,
            webhook_event=event,
            received_at=datetime.utcnow(),
        )

        with (
            patch.object(
                service,
                "get_email_by_message_id",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch("app.services.email_service.Email", return_value=test_email),
        ):
            # Act
            email = await service.store_email(sample_email_data, webhook_id, event)

            # Assert
            assert email is test_email
            assert email.webhook_id == webhook_id
            mock_db_session.add.assert_called_once()
            mock_db_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_store_existing_email(
        self,
        mock_db_session: AsyncMock,
        mock_attachment_service: AsyncMock,
        mock_storage_service: AsyncMock,
        sample_email_data: InboundEmailData,
        sample_email: Email,
    ) -> None:
        """Test storing an email that already exists."""
        # Arrange
        service = EmailService(
            db=mock_db_session,
            attachment_service=mock_attachment_service,
            storage=mock_storage_service,
        )

        # Mock get_email_by_message_id to return an existing email
        with patch.object(
            service,
            "get_email_by_message_id",
            new_callable=AsyncMock,
            return_value=sample_email,
        ):
            webhook_id = "test-webhook-id"
            event = "inbound_email"

            # Act
            email = await service.store_email(sample_email_data, webhook_id, event)

            # Assert
            assert email is sample_email
            mock_db_session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_webhook_without_attachments(
        self,
        mock_db_session: AsyncMock,
        mock_attachment_service: AsyncMock,
        mock_storage_service: AsyncMock,
        sample_webhook: MailchimpWebhook,
        sample_email: Email,
    ) -> None:
        """Test processing a webhook without attachments."""
        # Arrange
        service = EmailService(
            db=mock_db_session,
            attachment_service=mock_attachment_service,
            storage=mock_storage_service,
        )

        # Create a patch to control Email creation
        with patch.object(
            service, "store_email", new_callable=AsyncMock, return_value=sample_email
        ):
            # Act
            email = await service.process_webhook(sample_webhook)

            # Assert
            assert email is sample_email
            mock_attachment_service.process_attachments.assert_not_called()
            mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_webhook_with_attachments(
        self,
        mock_db_session: AsyncMock,
        mock_attachment_service: AsyncMock,
        mock_storage_service: AsyncMock,
        sample_webhook: MailchimpWebhook,
        sample_email: Email,
    ) -> None:
        """Test processing a webhook with attachments."""
        # Arrange
        sample_webhook.data.attachments = [
            EmailAttachment(
                name="test.txt", type="text/plain", size=10, content_id="test123"
            )
        ]
        service = EmailService(
            db=mock_db_session,
            attachment_service=mock_attachment_service,
            storage=mock_storage_service,
        )

        # Create a patch to control Email creation
        with patch.object(
            service, "store_email", new_callable=AsyncMock, return_value=sample_email
        ):
            # Act
            email = await service.process_webhook(sample_webhook)

            # Assert
            assert email is sample_email
            mock_attachment_service.process_attachments.assert_called_once_with(
                sample_email.id, sample_webhook.data.attachments
            )
            mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_webhook_error_handling(
        self,
        mock_db_session: AsyncMock,
        mock_attachment_service: AsyncMock,
        mock_storage_service: AsyncMock,
        sample_webhook: MailchimpWebhook,
    ) -> None:
        """Test error handling during webhook processing."""
        # Arrange
        service = EmailService(
            db=mock_db_session,
            attachment_service=mock_attachment_service,
            storage=mock_storage_service,
        )
        mock_db_session.execute.side_effect = Exception("Database error")

        # Act/Assert
        with pytest.raises(ValueError):
            await service.process_webhook(sample_webhook)

        mock_db_session.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_email_by_message_id(
        self,
        mock_db_session: AsyncMock,
        mock_attachment_service: AsyncMock,
        mock_storage_service: AsyncMock,
        sample_email: Email,
    ) -> None:
        """Test retrieving an email by message ID."""
        # Arrange
        message_id = "<test-message-id@example.com>"
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = (
            sample_email
        )

        # Patch the SQLAlchemy select function
        with patch("app.services.email_service.select") as mock_select:
            service = EmailService(
                db=mock_db_session,
                attachment_service=mock_attachment_service,
                storage=mock_storage_service,
            )

            # Act
            email = await service.get_email_by_message_id(message_id)

            # Assert
            assert email is sample_email
            mock_db_session.execute.assert_called_once()
            mock_select.assert_called_once()
