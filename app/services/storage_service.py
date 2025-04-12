"""Module providing Storage Service functionality for the services."""

import logging

import aioboto3  # type: ignore
import aiofiles
from botocore.exceptions import ClientError  # type: ignore

from app.core.config import settings

logger = logging.getLogger(__name__)


class StorageService:
    """Service for handling file storage operations.

    Can work with local filesystem or S3 depending on configuration.
    """

    def __init__(self, aws_credentials: dict[str, str] | None = None) -> None:
        """Initialize the storage service.

        Args:
            aws_credentials: Optional AWS credentials dictionary with
                aws_access_key_id, aws_secret_access_key, and region_name
        """
        self.use_s3 = settings.USE_S3_STORAGE
        self.bucket_name = settings.S3_BUCKET_NAME
        self.aws_credentials = aws_credentials or {
            "aws_access_key_id": settings.AWS_ACCESS_KEY_ID,
            "aws_secret_access_key": settings.AWS_SECRET_ACCESS_KEY,
            "region_name": settings.AWS_REGION,
        }

    async def save_file(
        self, file_data: bytes, object_key: str, content_type: str | None = None
    ) -> str:
        """Save a file to storage (either S3 or local filesystem).

        Args:
            file_data: Binary content of the file
            object_key: The key/path for the file
            content_type: MIME type of the file

        Returns:
            str: The storage URI (s3:// or file:// prefix)
        """
        if self.use_s3:
            return await self._save_to_s3(file_data, object_key, content_type)
        return await self._save_to_filesystem(file_data, object_key)

    async def _save_to_s3(
        self, file_data: bytes, object_key: str, content_type: str | None = None
    ) -> str:
        """Save a file to S3.

        Args:
            file_data: Binary content of the file
            object_key: The S3 object key
            content_type: MIME type of the file

        Returns:
            str: The S3 URI (s3://bucket-name/object-key)
        """
        try:
            extra_args = {}
            if content_type:
                extra_args["ContentType"] = content_type

            session = aioboto3.Session(**self.aws_credentials)

            async with session.client("s3") as s3:
                await s3.put_object(
                    Bucket=self.bucket_name,
                    Key=object_key,
                    Body=file_data,
                    **extra_args,
                )

            return f"s3://{self.bucket_name}/{object_key}"
        except ClientError as e:
            logger.error("Error uploading to S3: %s", str(e))
            raise

    async def _save_to_filesystem(self, file_data: bytes, relative_path: str) -> str:
        """Save a file to the local filesystem.

        Args:
            file_data: Binary content of the file
            relative_path: Path relative to the attachments base directory

        Returns:
            str: The file URI (file:///path/to/file)
        """
        full_path = settings.ATTACHMENTS_BASE_DIR / relative_path

        # Ensure directory exists
        full_path.parent.mkdir(parents=True, exist_ok=True)

        # Write file asynchronously
        async with aiofiles.open(full_path, "wb") as f:
            await f.write(file_data)

        return f"file://{full_path.absolute()}"

    async def get_file(self, uri: str) -> bytes | None:
        """Get file content from either S3 or filesystem.

        Args:
            uri: The storage URI (s3:// or file:// prefix)

        Returns:
            Optional[bytes]: The file content or None if not found
        """
        if uri.startswith("s3://"):
            return await self._get_from_s3(uri)
        if uri.startswith("file://"):
            return await self._get_from_filesystem(uri)
        logger.error("Unsupported URI scheme: %s", uri)
        return None

    async def _get_from_s3(self, uri: str) -> bytes | None:
        """Get file content from S3.

        Args:
            uri: The S3 URI (s3://bucket-name/object-key)

        Returns:
            Optional[bytes]: The file content or None if not found
        """
        try:
            # Parse bucket and key from URI
            # Format: s3://bucket-name/object-key
            parts = uri.replace("s3://", "").split("/", 1)
            bucket_name = parts[0]
            object_key = parts[1]

            session = aioboto3.Session(**self.aws_credentials)

            async with session.client("s3") as s3:
                response = await s3.get_object(Bucket=bucket_name, Key=object_key)

                async with response["Body"] as stream:
                    data = await stream.read()
                    return bytes(data)

        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                logger.warning("File not found in S3: %s", uri)
                return None
            logger.error("Error retrieving from S3: %s", str(e))
            raise

    async def _get_from_filesystem(self, uri: str) -> bytes | None:
        """Get file content from the filesystem.

        Args:
            uri: The file URI (file:///path/to/file)

        Returns:
            Optional[bytes]: The file content or None if not found
        """
        # Replace file:// prefix and convert to a Path object
        # This makes the code more robust across different systems
        if uri.startswith("file://"):
            uri = uri.replace("file://", "", 1)

        try:
            async with aiofiles.open(uri, "rb") as f:
                return await f.read()
        except FileNotFoundError:
            logger.warning("File not found: %s", uri)
            return None
        except Exception as e:
            logger.error("Error reading file: %s", str(e))
            raise


async def get_storage_service() -> StorageService:
    """Dependency function to get the storage service.

    Returns:
        StorageService: The storage service instance
    """
    return StorageService()
