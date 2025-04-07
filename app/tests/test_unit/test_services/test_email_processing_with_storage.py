import base64
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.email_data import EmailAttachment
from app.services.email_processing_service import EmailProcessingService


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


class TestEmailProcessingWithStorage:
    """Test suite for EmailProcessingService with storage service."""

    @pytest.mark.asyncio
    async def test_process_attachments(
        self,
        test_attachment: EmailAttachment,
        mock_storage_service: AsyncMock,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test processing attachments with storage service."""
        # Setup
        service = EmailProcessingService(mock_db_session, mock_storage_service)

        # Execute
        attachments = await service.process_attachments(1, [test_attachment])

        # Verify
        assert len(attachments) == 1
        attachment = attachments[0]
        assert attachment.email_id == 1
        assert attachment.filename == "test.pdf"
        assert attachment.content_type == "application/pdf"
        assert attachment.content_id == "test123"
        assert (
            attachment.storage_uri == "s3://test-bucket/attachments/1/abcd1234_test.pdf"
        )

        # Verify storage service was called with correct parameters
        mock_storage_service.save_file.assert_called_once()
        call_args = mock_storage_service.save_file.call_args[1]
        assert call_args["content_type"] == "application/pdf"
        assert isinstance(call_args["file_data"], bytes)
        assert "attachments/1/" in call_args["object_key"]

        # Verify db.add was called
        assert mock_db_session.add.called

    @pytest.mark.asyncio
    async def test_process_multiple_attachments(
        self,
        test_attachment: EmailAttachment,
        mock_storage_service: AsyncMock,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test processing multiple attachments."""
        # Setup
        service = EmailProcessingService(mock_db_session, mock_storage_service)

        attachment2 = EmailAttachment(
            name="image.jpg",
            type="image/jpeg",
            content=base64.b64encode(b"test image content").decode(),
            size=16,
        )

        mock_storage_service.save_file.side_effect = [
            "s3://test-bucket/attachments/1/abcd1234_test.pdf",
            "s3://test-bucket/attachments/1/efgh5678_image.jpg",
        ]

        # Execute
        attachments = await service.process_attachments(
            1, [test_attachment, attachment2]
        )

        # Verify
        assert len(attachments) == 2
        assert attachments[0].filename == "test.pdf"
        assert attachments[1].filename == "image.jpg"
        assert mock_storage_service.save_file.call_count == 2

        # Verify db.add was called twice
        assert mock_db_session.add.call_count == 2

    @pytest.mark.asyncio
    async def test_process_attachment_no_content(
        self, mock_storage_service: AsyncMock, mock_db_session: AsyncMock
    ) -> None:
        """Test processing attachment with no content."""
        # Setup
        service = EmailProcessingService(mock_db_session, mock_storage_service)

        attachment = EmailAttachment(
            name="empty.txt",
            type="text/plain",
            content="",  # Empty string instead of None
            size=0,
        )

        # Execute
        attachments = await service.process_attachments(1, [attachment])

        # Verify
        assert len(attachments) == 1
        attachment = attachments[0]
        assert attachment.filename == "empty.txt"
        assert not hasattr(attachment, "storage_uri") or attachment.storage_uri is None
        assert not mock_storage_service.save_file.called

        # Verify db.add was called once
        assert mock_db_session.add.call_count == 1
