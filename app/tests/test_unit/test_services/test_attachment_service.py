import base64
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.email_data import Attachment
from app.schemas.webhook_schemas import EmailAttachment
from app.services.attachment_service import AttachmentService
from app.services.storage_service import StorageService


@pytest.fixture
def mock_storage_service() -> AsyncMock:
    """Create a mock storage service."""
    mock = AsyncMock(spec=StorageService)
    mock.save_file = AsyncMock(return_value="s3://test-bucket/attachments/1/test.txt")
    return mock


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Create a mock db session."""
    session = AsyncMock(spec=AsyncSession)
    session.add = MagicMock()
    session.flush = AsyncMock()
    return session


@pytest.fixture
def sample_attachment() -> EmailAttachment:
    """Create a sample email attachment."""
    return EmailAttachment(
        name="test.txt",
        type="text/plain",
        content=base64.b64encode(b"Hello, world!").decode("utf-8"),
        content_id="test123",
        size=13,
    )


class TestAttachmentService:
    """Test suite for the AttachmentService."""

    @pytest.mark.asyncio
    async def test_process_attachments(
        self,
        mock_db_session: AsyncMock,
        mock_storage_service: AsyncMock,
        sample_attachment: EmailAttachment,
    ) -> None:
        """Test processing attachments."""
        # Arrange
        service = AttachmentService(db=mock_db_session, storage=mock_storage_service)
        email_id = 1
        attachments = [sample_attachment]

        # Act
        result = await service.process_attachments(email_id, attachments)

        # Assert
        assert len(result) == 1
        assert isinstance(result[0], Attachment)
        assert result[0].email_id == email_id
        assert result[0].filename == "test.txt"
        assert result[0].content_type == "text/plain"
        assert result[0].content_id == "test123"
        assert result[0].size == 13
        assert result[0].storage_uri == "s3://test-bucket/attachments/1/test.txt"

        # Verify interactions
        mock_storage_service.save_file.assert_called_once()
        mock_db_session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_empty_attachments(
        self, mock_db_session: AsyncMock, mock_storage_service: AsyncMock
    ) -> None:
        """Test processing an empty list of attachments."""
        # Arrange
        service = AttachmentService(db=mock_db_session, storage=mock_storage_service)
        email_id = 1

        # Act
        result = await service.process_attachments(email_id, [])

        # Assert
        assert isinstance(result, list)
        assert len(result) == 0
        mock_storage_service.save_file.assert_not_called()

    @pytest.mark.asyncio
    async def test_attachment_without_content(
        self,
        mock_db_session: AsyncMock,
        mock_storage_service: AsyncMock,
        sample_attachment: EmailAttachment,
    ) -> None:
        """Test processing an attachment without content."""
        # Arrange
        sample_attachment.content = None
        service = AttachmentService(db=mock_db_session, storage=mock_storage_service)
        email_id = 1

        # Act
        result = await service.process_attachments(email_id, [sample_attachment])

        # Assert
        assert len(result) == 1
        assert isinstance(result[0], Attachment)
        assert result[0].storage_uri is None
        mock_storage_service.save_file.assert_not_called()
        mock_db_session.add.assert_called_once()
