"""Tests for the attachment endpoints API."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.attachments import get_attachment
from app.models.email_data import Attachment
from app.services.storage_service import StorageService


@pytest.fixture
def mock_attachment() -> Attachment:
    """Create a mock attachment object."""
    return Attachment(
        id=1,
        email_id=1,
        filename="test_file.txt",
        content_type="text/plain",
        content=b"Test content",
        content_id="test123",
        size=12,
        storage_uri="attachments/1/test_file.txt",
    )


@pytest.mark.asyncio
async def test_get_attachment_from_storage(mock_attachment: Attachment) -> None:
    """Test successful retrieval of an attachment from storage."""
    # Mock DB session and query result
    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_db.execute.return_value = mock_result
    mock_result.scalar_one_or_none.return_value = mock_attachment

    # Mock storage service
    mock_storage = AsyncMock(spec=StorageService)
    mock_storage.get_file.return_value = b"File content from storage"

    # Call the endpoint
    response = await get_attachment(attachment_id=1, db=mock_db, storage=mock_storage)

    # Assertions
    mock_db.execute.assert_called_once()
    mock_storage.get_file.assert_called_once_with(mock_attachment.storage_uri)
    assert isinstance(response, Response)
    assert response.body == b"File content from storage"
    assert response.media_type == "text/plain"
    assert "filename" in response.headers["Content-Disposition"]


@pytest.mark.asyncio
async def test_get_attachment_from_db(mock_attachment: Attachment) -> None:
    """Test fallback to DB content if storage retrieval fails."""
    # Set up mocks
    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_db.execute.return_value = mock_result
    mock_result.scalar_one_or_none.return_value = mock_attachment

    # Storage service returns None (simulating failed retrieval)
    mock_storage = AsyncMock(spec=StorageService)
    mock_storage.get_file.return_value = None

    # Call the endpoint
    response = await get_attachment(attachment_id=1, db=mock_db, storage=mock_storage)

    # Assertions
    mock_db.execute.assert_called_once()
    mock_storage.get_file.assert_called_once_with(mock_attachment.storage_uri)
    assert isinstance(response, Response)
    assert response.body == mock_attachment.content
    assert response.media_type == "text/plain"


@pytest.mark.asyncio
async def test_attachment_not_found() -> None:
    """Test handling of non-existent attachment ID."""
    # Set up mocks
    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_db.execute.return_value = mock_result
    mock_result.scalar_one_or_none.return_value = None  # No attachment found

    mock_storage = AsyncMock(spec=StorageService)

    # Call the endpoint and check for exception
    with pytest.raises(HTTPException) as exc_info:
        await get_attachment(attachment_id=999, db=mock_db, storage=mock_storage)

    assert exc_info.value.status_code == 404
    assert "Attachment not found" in exc_info.value.detail


@pytest.mark.asyncio
async def test_attachment_content_not_available(mock_attachment: Attachment) -> None:
    """Test handling when attachment content is not available."""
    # Create attachment with no content and no storage_uri
    attachment_no_content = Attachment(
        id=2,
        email_id=1,
        filename="empty.txt",
        content_type="text/plain",
        content=None,  # No content
        content_id="empty123",
        size=0,
        storage_uri=None,  # No storage URI
    )

    # Set up mocks
    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_db.execute.return_value = mock_result
    mock_result.scalar_one_or_none.return_value = attachment_no_content

    mock_storage = AsyncMock(spec=StorageService)
    mock_storage.get_file.return_value = None  # Storage retrieval fails

    # Call the endpoint and check for exception
    with pytest.raises(HTTPException) as exc_info:
        await get_attachment(attachment_id=2, db=mock_db, storage=mock_storage)

    assert exc_info.value.status_code == 404
    assert "Attachment content not available" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_attachment_complex_filename(mock_attachment: Attachment) -> None:
    """Test handling of attachments with complex filenames."""
    # Modify the attachment to have a filename with spaces and special chars
    mock_attachment.filename = "test file (1).txt"

    # Set up mocks
    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_db.execute.return_value = mock_result
    mock_result.scalar_one_or_none.return_value = mock_attachment

    mock_storage = AsyncMock(spec=StorageService)
    mock_storage.get_file.return_value = b"File content"

    # Call the endpoint
    response = await get_attachment(attachment_id=1, db=mock_db, storage=mock_storage)

    # Verify filename handling in Content-Disposition header
    assert "filename" in response.headers["Content-Disposition"]
    assert "test file (1).txt" in response.headers["Content-Disposition"]
