import os
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from botocore.exceptions import ClientError  # type: ignore

from app.services.storage_service import StorageService


@pytest.fixture
def test_file_content() -> bytes:
    return b"This is test file content"


@pytest.fixture
def mock_s3_client() -> AsyncMock:
    """Fixture for mocking S3 client."""
    mock_client = AsyncMock()
    mock_stream = AsyncMock()
    mock_stream.__aenter__.return_value = AsyncMock()
    mock_stream.__aenter__.return_value.read = AsyncMock(
        return_value=b"This is test file content"
    )

    mock_client.__aenter__.return_value = mock_client
    mock_client.put_object = AsyncMock()
    mock_client.get_object = AsyncMock(return_value={"Body": mock_stream})
    return mock_client


class TestStorageService:
    """Test suite for StorageService."""

    def test_init_local_storage(self) -> None:
        """Test initialization with local storage."""
        with patch("app.services.storage_service.settings") as mock_settings:
            mock_settings.USE_S3_STORAGE = False
            service = StorageService()
            assert service.use_s3 is False

    def test_init_s3_storage(self) -> None:
        """Test initialization with S3 storage."""
        with patch("app.services.storage_service.settings") as mock_settings:
            mock_settings.USE_S3_STORAGE = True
            mock_settings.S3_BUCKET_NAME = "test-bucket"
            service = StorageService()
            assert service.use_s3 is True
            assert service.bucket_name == "test-bucket"

    @pytest.mark.asyncio
    async def test_save_file_local(
        self, test_file_content: bytes, tmp_path: Any
    ) -> None:
        """Test saving file to local filesystem."""
        with patch("app.services.storage_service.settings") as mock_settings:
            mock_settings.USE_S3_STORAGE = False
            mock_settings.ATTACHMENTS_BASE_DIR = tmp_path

            service = StorageService()
            result = await service.save_file(test_file_content, "test/test_file.txt")

            assert result.startswith("file://")
            assert "test/test_file.txt" in result

            # Verify file was saved
            file_path = tmp_path / "test" / "test_file.txt"
            assert file_path.exists()
            with open(file_path, "rb") as f:
                assert f.read() == test_file_content

    @pytest.mark.asyncio
    async def test_save_file_s3(
        self, test_file_content: bytes, mock_s3_client: AsyncMock
    ) -> None:
        """Test saving file to S3."""
        with (
            patch("app.services.storage_service.settings") as mock_settings,
            patch("aioboto3.Session") as mock_session,
        ):
            mock_settings.USE_S3_STORAGE = True
            mock_settings.S3_BUCKET_NAME = "test-bucket"
            mock_session.return_value.client.return_value = mock_s3_client

            service = StorageService()
            result = await service.save_file(
                test_file_content, "test/test_file.txt", "text/plain"
            )

            assert result == "s3://test-bucket/test/test_file.txt"

            # Verify S3 client was called with correct parameters
            mock_s3_client.put_object.assert_called_once_with(
                Bucket="test-bucket",
                Key="test/test_file.txt",
                Body=test_file_content,
                ContentType="text/plain",
            )

    @pytest.mark.asyncio
    async def test_get_file_local(
        self, test_file_content: bytes, tmp_path: Any
    ) -> None:
        """Test retrieving file from local filesystem."""
        file_path = tmp_path / "test_file.txt"
        os.makedirs(file_path.parent, exist_ok=True)
        with open(file_path, "wb") as f:
            f.write(test_file_content)

        service = StorageService()
        result = await service.get_file(f"file://{file_path}")

        assert result == test_file_content

    @pytest.mark.asyncio
    async def test_get_file_local_not_found(self) -> None:
        """Test retrieving non-existent file from local filesystem."""
        service = StorageService()
        result = await service.get_file("file:///nonexistent/path.txt")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_file_s3(
        self, test_file_content: bytes, mock_s3_client: AsyncMock
    ) -> None:
        """Test retrieving file from S3."""
        with patch("aioboto3.Session") as mock_session:
            mock_session.return_value.client.return_value = mock_s3_client

            service = StorageService()
            result = await service.get_file("s3://test-bucket/test/test_file.txt")

            assert result == test_file_content

            # Verify S3 client was called with correct parameters
            mock_s3_client.get_object.assert_called_once_with(
                Bucket="test-bucket", Key="test/test_file.txt"
            )

    @pytest.mark.asyncio
    async def test_get_file_s3_not_found(self, mock_s3_client: AsyncMock) -> None:
        """Test retrieving non-existent file from S3."""
        with patch("aioboto3.Session") as mock_session:
            mock_s3_client.__aenter__.return_value.get_object.side_effect = ClientError(
                {"Error": {"Code": "NoSuchKey"}}, "get_object"
            )
            mock_session.return_value.client.return_value = mock_s3_client

            service = StorageService()
            result = await service.get_file("s3://test-bucket/nonexistent.txt")

            assert result is None

    @pytest.mark.asyncio
    async def test_get_file_invalid_uri(self) -> None:
        """Test retrieving file with invalid URI scheme."""
        service = StorageService()
        result = await service.get_file("invalid://test-bucket/test.txt")

        assert result is None

    @pytest.mark.asyncio
    async def test_custom_aws_credentials(
        self, test_file_content: bytes, mock_s3_client: AsyncMock
    ) -> None:
        """Test saving file to S3 with custom AWS credentials."""
        with (
            patch("app.services.storage_service.settings") as mock_settings,
            patch("aioboto3.Session") as mock_session,
        ):
            mock_settings.USE_S3_STORAGE = True
            mock_settings.S3_BUCKET_NAME = "test-bucket"
            mock_session.return_value.client.return_value = mock_s3_client

            custom_credentials = {
                "aws_access_key_id": "custom-access-key",
                "aws_secret_access_key": "custom-secret-key",
                "region_name": "custom-region",
            }

            service = StorageService(aws_credentials=custom_credentials)
            await service.save_file(test_file_content, "test/test_file.txt")

            # Verify Session was created with custom credentials
            mock_session.assert_called_once_with(
                aws_access_key_id="custom-access-key",
                aws_secret_access_key="custom-secret-key",
                region_name="custom-region",
            )
