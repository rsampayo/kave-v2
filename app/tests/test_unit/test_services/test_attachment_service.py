"""Module providing Test Attachment Service functionality for the tests test unit test services."""

import base64
from unittest.mock import AsyncMock, MagicMock, patch

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
        base64=True,
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

    @pytest.mark.asyncio
    async def test_process_attachments_with_db_session(self, db_session: AsyncSession):
        """Test the process_attachments method with a real database session."""
        # Arrange
        email_id = 1
        attachments = [
            EmailAttachment(
                name="test.txt",
                type="text/plain",
                content="SGVsbG8gV29ybGQ=",  # "Hello World" in base64
                content_id="test123",
                size=11,
                base64=True,
            )
        ]
        # Create a mock storage service
        mock_storage = AsyncMock(spec=StorageService)

        # Act
        service = AttachmentService(db=db_session, storage=mock_storage)
        result = await service.process_attachments(email_id, attachments)

        # Assert
        assert len(result) == 1
        assert isinstance(result[0], Attachment)
        assert result[0].email_id == email_id
        assert result[0].filename == "test.txt"
        assert result[0].content_type == "text/plain"
        assert result[0].content_id == "test123"
        assert result[0].size == 11

        # Add assertions for storage_uri if needed

        # No need to verify db_session.add since it's a real session, not a mock
        assert result[0].storage_uri is not None  # Verify the storage URI was set

    @pytest.mark.asyncio
    async def test_process_attachments_dispatches_ocr_task(self):
        """Test that process_attachments dispatches the OCR task for PDF attachments."""
        # Arrange
        mock_db_session = AsyncMock(spec=AsyncSession)
        mock_storage = AsyncMock(spec=StorageService)
        mock_storage.save_file = AsyncMock(return_value="test-storage-uri")

        # Create sample attachment data
        pdf_attachment_data = EmailAttachment(
            name="test.pdf",
            type="application/pdf",
            content=base64.b64encode(b"PDF content").decode("utf-8"),
            content_id="pdf123",
            size=123,
        )

        non_pdf_attachment_data = EmailAttachment(
            name="test.jpg",
            type="image/jpeg",
            content=base64.b64encode(b"JPG content").decode("utf-8"),
            content_id="jpg123",
            size=456,
        )

        # Create service instance
        service = AttachmentService(db=mock_db_session, storage=mock_storage)

        # Test dispatching OCR task
        with patch(
            "app.services.attachment_service.process_pdf_attachment"
        ) as mock_process_pdf_attachment:
            # Configure mock DB to set IDs when add is called
            mock_attachment_pdf = MagicMock(spec=Attachment)
            mock_attachment_pdf.id = None  # Start with no ID
            mock_attachment_pdf.content_type = "application/pdf"
            mock_attachment_pdf.filename = "test.pdf"

            mock_attachment_jpg = MagicMock(spec=Attachment)
            mock_attachment_jpg.id = None  # Start with no ID
            mock_attachment_jpg.content_type = "image/jpeg"
            mock_attachment_jpg.filename = "test.jpg"

            # Mock the Attachment constructor to return our mock objects
            with patch("app.services.attachment_service.Attachment") as MockAttachment:
                MockAttachment.side_effect = [mock_attachment_pdf, mock_attachment_jpg]

                # Mock flush to set IDs
                async def mock_flush(objects=None):
                    if objects is None or mock_attachment_pdf in objects:
                        mock_attachment_pdf.id = 1
                    if objects is None or mock_attachment_jpg in objects:
                        mock_attachment_jpg.id = 2

                mock_db_session.flush = AsyncMock(side_effect=mock_flush)

                # Call the method with both PDF and non-PDF attachments
                attachments = await service.process_attachments(
                    email_id=123,
                    attachments=[pdf_attachment_data, non_pdf_attachment_data],
                )

                # Verify both attachments were processed
                assert len(attachments) == 2

                # Verify the OCR task was called only for the PDF
                mock_process_pdf_attachment.delay.assert_called_once_with(
                    attachment_id=1
                )

                # Verify the task was not called for the non-PDF attachment
                assert mock_process_pdf_attachment.delay.call_count == 1
