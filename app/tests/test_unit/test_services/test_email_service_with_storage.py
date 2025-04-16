"""Tests for EmailService with storage integration."""

import base64
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from app.models.email_data import EmailAttachment
from app.services.attachment_service import AttachmentService
from app.services.email_service import EmailService


@pytest.fixture
def test_attachment() -> EmailAttachment:
    """Fixture for creating a test EmailAttachment."""
    return EmailAttachment(
        name="test.pdf",
        type="application/pdf",
        content=base64.b64encode(b"test PDF content").decode(),
        content_id="test123",
        size=15,
    )


@pytest.fixture
def mock_storage_service() -> AsyncMock:
    """Fixture for mocking StorageService."""
    mock = AsyncMock()
    mock.save_file.return_value = "s3://test-bucket/attachments/1/abcd1234_test.pdf"
    return mock


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Fixture for mocking AsyncSession."""
    mock = AsyncMock()
    # Make add method a normal function instead of a coroutine
    mock.add = MagicMock()
    mock.flush = AsyncMock()
    return mock


@pytest.fixture
def mock_attachment_service() -> AsyncMock:
    """Fixture for mocking AttachmentService."""
    mock = AsyncMock(spec=AttachmentService)
    mock.process_attachments.return_value = []
    return mock


class TestEmailServiceWithStorage:
    """Test suite for EmailService with storage service."""

    @pytest.mark.asyncio
    async def test_delegating_to_attachment_service(
        self,
        test_attachment: EmailAttachment,
        mock_storage_service: AsyncMock,
        mock_db_session: AsyncMock,
        mock_attachment_service: AsyncMock,
    ) -> None:
        """Test that EmailService properly delegates to AttachmentService."""
        # Setup
        service = EmailService(
            mock_db_session, mock_attachment_service, mock_storage_service
        )
        email_id = 123
        attachments = [test_attachment]

        # Create a mock email to be returned by store_email
        mock_email = Mock()
        mock_email.id = email_id

        # Create a mock webhook with attachments
        mock_webhook = MagicMock()
        mock_webhook.data = MagicMock()
        mock_webhook.data.attachments = attachments
        mock_webhook.webhook_id = "test-webhook-123"
        mock_webhook.event = "inbound_email"

        # Mock necessary methods to avoid coroutine issues
        with (
            patch.object(service, "store_email", return_value=mock_email),
            patch.object(service, "get_email_by_message_id", return_value=None),
        ):
            # Process the webhook
            await service.process_webhook(mock_webhook)

        # Verify that the attachment service was called with correct params
        mock_attachment_service.process_attachments.assert_called_once_with(
            email_id, attachments
        )
