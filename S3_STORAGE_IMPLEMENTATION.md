# Heroku Attachment Storage Implementation

## Overview

This document provides a detailed implementation plan for optimizing attachment storage when deploying the FastAPI application on Heroku. It addresses **Step 3.2** from the Refactoring Plan, focusing on moving attachment storage from the database to a cloud storage solution while maintaining robust functionality.

## Problem Statement

The current implementation has two key issues for Heroku deployment:

1. **Binary data storage in database**: Storing attachment content directly in the database (`content` column) can cause:
   - Database size bloat and performance issues
   - Increased backup time and costs
   - Slower query performance
   
2. **Filesystem storage on Heroku's ephemeral filesystem**: Heroku's dynos have an ephemeral filesystem that:
   - Does not persist between dyno restarts
   - Is not shared between multiple dynos when scaling
   - Has limited storage capacity

## Solution: Amazon S3 Storage with Database References

We'll implement a flexible solution that:
- Uses S3 for production deployments on Heroku
- Maintains file system storage capability for local development
- Removes binary content from the database
- Stores standardized URIs (`s3://` or `file://`) in the database

## Implementation Steps

### 1. Set Up Amazon S3 Bucket

1. Create an S3 bucket in the AWS console:
   - Region: Choose region closest to your app's users
   - Access control: Block all public access
   - Versioning: Enabled (recommended for data safety)
   - Encryption: Enable SSE-S3 encryption
   
2. Configure CORS (if web access to files is needed):
```json
[
    {
        "AllowedHeaders": ["*"],
        "AllowedMethods": ["GET"],
        "AllowedOrigins": ["https://your-app-domain.herokuapp.com"],
        "ExposeHeaders": [],
        "MaxAgeSeconds": 3000
    }
]
```

3. Create an IAM user with limited permissions:
   - Create a policy granting only necessary S3 permissions:
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:PutObject",
                "s3:GetObject",
                "s3:DeleteObject"
            ],
            "Resource": "arn:aws:s3:::your-bucket-name/*"
        },
        {
            "Effect": "Allow",
            "Action": "s3:ListBucket",
            "Resource": "arn:aws:s3:::your-bucket-name"
        }
    ]
}
```
   - Attach this policy to a new IAM user
   - Generate and securely store access key and secret key

### 2. Add AWS SDK Dependencies

Add the following dependencies to your requirements:

```bash
pip install boto3==1.34.0 aioboto3==12.3.0
```

Update the requirements file (`requirements/base.txt` or equivalent):

```
boto3>=1.34.0,<1.35.0
aioboto3>=12.3.0,<13.0.0
```

### 3. Update Configuration in `app/core/config.py`

Add the following S3 settings to your configuration class:

```python
# Add to app/core/config.py in the Settings class
S3_BUCKET_NAME: str = ""
AWS_ACCESS_KEY_ID: str = ""
AWS_SECRET_ACCESS_KEY: str = ""
AWS_REGION: str = "us-east-1"  # Default region
USE_S3_STORAGE: bool = False  # Default to False for development
```

### 4. Create Storage Service Module

Create a new file `app/services/storage_service.py`:

```python
import logging
from pathlib import Path
from typing import BinaryIO, Optional, Union

import aioboto3
from botocore.exceptions import ClientError

from app.core.config import settings

logger = logging.getLogger(__name__)


class StorageService:
    """Service for handling file storage operations.
    
    Can work with local filesystem or S3 depending on configuration.
    """
    
    def __init__(self):
        """Initialize the storage service."""
        self.use_s3 = settings.USE_S3_STORAGE
        self.bucket_name = settings.S3_BUCKET_NAME
        
    async def save_file(self, 
                        file_data: bytes, 
                        object_key: str, 
                        content_type: Optional[str] = None) -> str:
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
        else:
            return await self._save_to_filesystem(file_data, object_key)
    
    async def _save_to_s3(self, 
                         file_data: bytes, 
                         object_key: str, 
                         content_type: Optional[str] = None) -> str:
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
                
            session = aioboto3.Session(
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_REGION
            )
            
            async with session.client("s3") as s3:
                await s3.put_object(
                    Bucket=self.bucket_name,
                    Key=object_key,
                    Body=file_data,
                    **extra_args
                )
                
            return f"s3://{self.bucket_name}/{object_key}"
        except ClientError as e:
            logger.error(f"Error uploading to S3: {str(e)}")
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
        
        # Write file
        with open(full_path, "wb") as f:
            f.write(file_data)
            
        return f"file://{full_path.absolute()}"
    
    async def get_file(self, uri: str) -> Optional[bytes]:
        """Get file content from either S3 or filesystem.
        
        Args:
            uri: The storage URI (s3:// or file:// prefix)
            
        Returns:
            Optional[bytes]: The file content or None if not found
        """
        if uri.startswith("s3://"):
            return await self._get_from_s3(uri)
        elif uri.startswith("file://"):
            return await self._get_from_filesystem(uri)
        else:
            logger.error(f"Unsupported URI scheme: {uri}")
            return None
    
    async def _get_from_s3(self, uri: str) -> Optional[bytes]:
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
            
            session = aioboto3.Session(
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_REGION
            )
            
            async with session.client("s3") as s3:
                response = await s3.get_object(
                    Bucket=bucket_name,
                    Key=object_key
                )
                
                async with response["Body"] as stream:
                    return await stream.read()
                    
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                logger.warning(f"File not found in S3: {uri}")
                return None
            logger.error(f"Error retrieving from S3: {str(e)}")
            raise
    
    async def _get_from_filesystem(self, uri: str) -> Optional[bytes]:
        """Get file content from the filesystem.
        
        Args:
            uri: The file URI (file:///path/to/file)
            
        Returns:
            Optional[bytes]: The file content or None if not found
        """
        path = uri.replace("file://", "")
        try:
            with open(path, "rb") as f:
                return f.read()
        except FileNotFoundError:
            logger.warning(f"File not found: {path}")
            return None
        except Exception as e:
            logger.error(f"Error reading file: {str(e)}")
            raise


async def get_storage_service() -> StorageService:
    """Dependency function to get the storage service.
    
    Returns:
        StorageService: The storage service instance
    """
    return StorageService()
```

### 5. Update Attachment Model

Update the `Attachment` model in `app/models/email_data.py`:

```python
class Attachment(Base):
    """Model representing an email attachment."""

    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
        comment="Unique identifier for the attachment record",
    )
    email_id: Mapped[int] = mapped_column(
        ForeignKey("emails.id", ondelete="CASCADE"),
        comment="Foreign key to the parent email",
    )
    filename: Mapped[str] = mapped_column(
        String(255), comment="Original filename of the attachment"
    )
    content_type: Mapped[str] = mapped_column(
        String(100), comment="MIME type of the attachment"
    )
    content_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Content-ID for referencing in HTML (e.g., for inline images)",
    )
    size: Mapped[Optional[int]] = mapped_column(
        nullable=True, comment="Size of the attachment in bytes"
    )

    # Storage information - update to storage URI
    storage_uri: Mapped[str] = mapped_column(
        String(1024),
        comment="URI for the stored file (s3:// or file:// scheme)"
    )
    
    # Remove content column or make it nullable with a migration
    # content: Mapped[Optional[bytes]] = mapped_column(nullable=True)

    # Relationship with the parent email
    email: Mapped["Email"] = relationship("Email", back_populates="attachments")
```

### 6. Create Alembic Migration

Generate a migration using alembic:

```bash
alembic revision --autogenerate -m "Update attachment model to use storage_uri"
```

Review the generated migration and ensure it:
1. Adds the `storage_uri` column
2. Makes the `content` column nullable (as a first step before removal)

Run the migration:

```bash
alembic upgrade head
```

### 7. Update Email Processing Service

Update `app/services/email_processing_service.py`:

```python
# Add import
from app.services.storage_service import StorageService, get_storage_service

class EmailProcessingService:
    """Service responsible for processing emails and attachments."""

    def __init__(self, db: AsyncSession, storage: StorageService):
        """Initialize the email processing service.
        
        Args:
            db: Database session
            storage: Storage service for handling attachments
        """
        self.db = db
        self.storage = storage

    # ... other methods ...

    async def process_attachments(
        self, email_id: int, attachments: List[EmailAttachment]
    ) -> List[Attachment]:
        """Process and store email attachments.
        
        Args:
            email_id: ID of the parent email
            attachments: List of attachment data from the webhook
            
        Returns:
            List[Attachment]: The created attachment models
        """
        result = []

        for attach_data in attachments:
            # Get filename and generate a unique object key
            filename = attach_data.name
            unique_id = str(uuid.uuid4())[:8]
            object_key = f"attachments/{email_id}/{unique_id}_{filename}"

            # Create the attachment model (without content)
            attachment = Attachment(
                email_id=email_id,
                filename=filename,
                content_type=attach_data.type,
                content_id=attach_data.content_id,
                size=attach_data.size,
                # Leave storage_uri empty initially
            )

            # If attachment has content, decode and save it
            if attach_data.content:
                # Decode base64 content
                content = base64.b64decode(attach_data.content)
                
                # Save to storage service (S3 or filesystem based on settings)
                storage_uri = await self.storage.save_file(
                    file_data=content,
                    object_key=object_key,
                    content_type=attach_data.type
                )
                
                # Update the model with the storage URI
                attachment.storage_uri = storage_uri

            self.db.add(attachment)
            result.append(attachment)

        return result


# Update the dependency function
async def get_email_service(
    db: AsyncSession = Depends(get_db),
    storage: StorageService = Depends(get_storage_service),
) -> EmailProcessingService:
    """Dependency function to get the email processing service."""
    return EmailProcessingService(db, storage)
```

### 8. Create API Endpoint for File Access

Create a new file `app/api/endpoints/attachments.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.email_data import Attachment
from app.services.storage_service import StorageService, get_storage_service

router = APIRouter()


@router.get("/{attachment_id}")
async def get_attachment(
    attachment_id: int,
    db: AsyncSession = Depends(get_db),
    storage: StorageService = Depends(get_storage_service),
):
    """Get an attachment file by ID.
    
    Args:
        attachment_id: The ID of the attachment
        db: Database session
        storage: Storage service
        
    Returns:
        Response: The attachment file content
        
    Raises:
        HTTPException: If attachment not found or content unavailable
    """
    # Query for the attachment by ID
    result = await db.execute(select(Attachment).where(Attachment.id == attachment_id))
    attachment = result.scalar_one_or_none()
    
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")
    
    # Get the file content from storage
    file_data = await storage.get_file(attachment.storage_uri)
    
    if not file_data:
        raise HTTPException(
            status_code=404, 
            detail="Attachment content not available"
        )
    
    # Return the file as a response with the correct content type
    return Response(
        content=file_data,
        media_type=attachment.content_type,
        headers={"Content-Disposition": f'attachment; filename="{attachment.filename}"'}
    )
```

Update `app/api/api.py` to include the new router:

```python
# Add import
from app.api.endpoints import attachments

# Add to your API router inclusion
api_router.include_router(
    attachments.router, 
    prefix="/attachments", 
    tags=["attachments"]
)
```

### 9. Heroku Configuration

1. Set up the Heroku app if not already created:
```bash
heroku create your-app-name
```

2. Add the necessary environment variables to Heroku:
```bash
heroku config:set S3_BUCKET_NAME=your-bucket-name
heroku config:set AWS_ACCESS_KEY_ID=your-access-key
heroku config:set AWS_SECRET_ACCESS_KEY=your-secret-key
heroku config:set AWS_REGION=your-region
heroku config:set USE_S3_STORAGE=true
```

3. Create a `Procfile` in the project root:
```
release: alembic upgrade head
web: uvicorn app.main:app --host=0.0.0.0 --port=${PORT:-8000}
```

4. Add a `runtime.txt` to specify the Python version:
```
python-3.11.8
```

5. Deploy to Heroku:
```bash
git push heroku main
```

## TDD Tests for Implementation

Following Test-Driven Development, create the following tests before implementing the production code:

### 1. Storage Service Unit Tests

Create `app/tests/test_services/test_storage_service.py`:

```python
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.storage_service import StorageService


@pytest.fixture
def test_file_content():
    return b"This is test file content"


@pytest.fixture
def mock_s3_client():
    """Fixture for mocking S3 client."""
    mock_client = AsyncMock()
    mock_stream = AsyncMock()
    mock_stream.__aenter__.return_value = AsyncMock()
    mock_stream.__aenter__.return_value.read = AsyncMock(return_value=b"This is test file content")
    
    mock_client.__aenter__.return_value = mock_client
    mock_client.put_object = AsyncMock()
    mock_client.get_object = AsyncMock(return_value={"Body": mock_stream})
    return mock_client


class TestStorageService:
    """Test suite for StorageService."""
    
    def test_init_local_storage(self):
        """Test initialization with local storage."""
        with patch("app.services.storage_service.settings") as mock_settings:
            mock_settings.USE_S3_STORAGE = False
            service = StorageService()
            assert service.use_s3 is False
    
    def test_init_s3_storage(self):
        """Test initialization with S3 storage."""
        with patch("app.services.storage_service.settings") as mock_settings:
            mock_settings.USE_S3_STORAGE = True
            mock_settings.S3_BUCKET_NAME = "test-bucket"
            service = StorageService()
            assert service.use_s3 is True
            assert service.bucket_name == "test-bucket"
    
    @pytest.mark.asyncio
    async def test_save_file_local(self, test_file_content, tmp_path):
        """Test saving file to local filesystem."""
        with patch("app.services.storage_service.settings") as mock_settings:
            mock_settings.USE_S3_STORAGE = False
            mock_settings.ATTACHMENTS_BASE_DIR = tmp_path
            
            service = StorageService()
            result = await service.save_file(test_file_content, "test/test_file.txt")
            
            assert result.startswith("file://")
            assert "test/test_file.txt" in result
            
            # Verify file was saved
            file_path = tmp_path / "test/test_file.txt"
            assert file_path.exists()
            with open(file_path, "rb") as f:
                assert f.read() == test_file_content
    
    @pytest.mark.asyncio
    async def test_save_file_s3(self, test_file_content, mock_s3_client):
        """Test saving file to S3."""
        with patch("app.services.storage_service.settings") as mock_settings, \
             patch("aioboto3.Session") as mock_session:
            mock_settings.USE_S3_STORAGE = True
            mock_settings.S3_BUCKET_NAME = "test-bucket"
            mock_session.return_value.client.return_value = mock_s3_client
            
            service = StorageService()
            result = await service.save_file(
                test_file_content, 
                "test/test_file.txt",
                "text/plain"
            )
            
            assert result == "s3://test-bucket/test/test_file.txt"
            
            # Verify S3 client was called with correct parameters
            mock_s3_client.put_object.assert_called_once_with(
                Bucket="test-bucket",
                Key="test/test_file.txt",
                Body=test_file_content,
                ContentType="text/plain"
            )
    
    @pytest.mark.asyncio
    async def test_get_file_local(self, test_file_content, tmp_path):
        """Test retrieving file from local filesystem."""
        file_path = tmp_path / "test_file.txt"
        with open(file_path, "wb") as f:
            f.write(test_file_content)
        
        service = StorageService()
        result = await service.get_file(f"file://{file_path}")
        
        assert result == test_file_content
    
    @pytest.mark.asyncio
    async def test_get_file_local_not_found(self):
        """Test retrieving non-existent file from local filesystem."""
        service = StorageService()
        result = await service.get_file("file:///nonexistent/path.txt")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_file_s3(self, test_file_content, mock_s3_client):
        """Test retrieving file from S3."""
        with patch("aioboto3.Session") as mock_session:
            mock_session.return_value.client.return_value = mock_s3_client
            
            service = StorageService()
            result = await service.get_file("s3://test-bucket/test/test_file.txt")
            
            assert result == test_file_content
            
            # Verify S3 client was called with correct parameters
            mock_s3_client.get_object.assert_called_once_with(
                Bucket="test-bucket",
                Key="test/test_file.txt"
            )
    
    @pytest.mark.asyncio
    async def test_get_file_s3_not_found(self, mock_s3_client):
        """Test retrieving non-existent file from S3."""
        with patch("aioboto3.Session") as mock_session:
            mock_s3_client.__aenter__.return_value.get_object.side_effect = \
                ClientError({"Error": {"Code": "NoSuchKey"}}, "get_object")
            mock_session.return_value.client.return_value = mock_s3_client
            
            service = StorageService()
            result = await service.get_file("s3://test-bucket/nonexistent.txt")
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_get_file_invalid_uri(self):
        """Test retrieving file with invalid URI scheme."""
        service = StorageService()
        result = await service.get_file("invalid://test-bucket/test.txt")
        
        assert result is None
```

### 2. Email Processing Service Tests

Add tests for the updated EmailProcessingService to `app/tests/test_services/test_email_processing_service.py`:

```python
import base64
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.email_data import Attachment, EmailAttachment
from app.services.email_processing_service import EmailProcessingService


@pytest.fixture
def test_attachment():
    """Fixture for creating a test EmailAttachment."""
    return EmailAttachment(
        name="test.pdf",
        type="application/pdf",
        content=base64.b64encode(b"test PDF content").decode(),
        content_id="test123",
        size=15
    )


@pytest.fixture
def mock_storage_service():
    """Fixture for mocking StorageService."""
    mock = AsyncMock()
    mock.save_file.return_value = "s3://test-bucket/attachments/1/abcd1234_test.pdf"
    return mock


class TestEmailProcessingService:
    """Test suite for EmailProcessingService."""
    
    @pytest.mark.asyncio
    async def test_process_attachments(self, test_attachment, mock_storage_service):
        """Test processing attachments with storage service."""
        # Setup
        mock_db = AsyncMock()
        service = EmailProcessingService(mock_db, mock_storage_service)
        
        # Execute
        attachments = await service.process_attachments(1, [test_attachment])
        
        # Verify
        assert len(attachments) == 1
        attachment = attachments[0]
        assert attachment.email_id == 1
        assert attachment.filename == "test.pdf"
        assert attachment.content_type == "application/pdf"
        assert attachment.content_id == "test123"
        assert attachment.storage_uri == "s3://test-bucket/attachments/1/abcd1234_test.pdf"
        
        # Verify storage service was called with correct parameters
        mock_storage_service.save_file.assert_called_once()
        call_args = mock_storage_service.save_file.call_args[1]
        assert call_args["content_type"] == "application/pdf"
        assert isinstance(call_args["file_data"], bytes)
        assert "attachments/1/" in call_args["object_key"]
    
    @pytest.mark.asyncio
    async def test_process_multiple_attachments(self, test_attachment, mock_storage_service):
        """Test processing multiple attachments."""
        # Setup
        mock_db = AsyncMock()
        service = EmailProcessingService(mock_db, mock_storage_service)
        
        attachment2 = EmailAttachment(
            name="image.jpg",
            type="image/jpeg",
            content=base64.b64encode(b"test image content").decode(),
            size=16
        )
        
        mock_storage_service.save_file.side_effect = [
            "s3://test-bucket/attachments/1/abcd1234_test.pdf",
            "s3://test-bucket/attachments/1/efgh5678_image.jpg"
        ]
        
        # Execute
        attachments = await service.process_attachments(1, [test_attachment, attachment2])
        
        # Verify
        assert len(attachments) == 2
        assert attachments[0].filename == "test.pdf"
        assert attachments[1].filename == "image.jpg"
        assert mock_storage_service.save_file.call_count == 2
    
    @pytest.mark.asyncio
    async def test_process_attachment_no_content(self, mock_storage_service):
        """Test processing attachment with no content."""
        # Setup
        mock_db = AsyncMock()
        service = EmailProcessingService(mock_db, mock_storage_service)
        
        attachment = EmailAttachment(
            name="empty.txt",
            type="text/plain",
            content=None,
            size=0
        )
        
        # Execute
        attachments = await service.process_attachments(1, [attachment])
        
        # Verify
        assert len(attachments) == 1
        attachment = attachments[0]
        assert attachment.filename == "empty.txt"
        assert not hasattr(attachment, "storage_uri") or attachment.storage_uri is None
        assert not mock_storage_service.save_file.called
```

### 3. API Endpoint Tests

Create `app/tests/test_api/test_attachment_endpoints.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.models.email_data import Attachment


@pytest.fixture
def mock_db_session(monkeypatch):
    """Fixture for mocking database session."""
    mock = AsyncMock()
    
    # Setup mock for the query result
    mock_result = AsyncMock()
    mock.execute.return_value = mock_result
    
    monkeypatch.setattr("app.api.endpoints.attachments.get_db", lambda: mock)
    return mock, mock_result


@pytest.fixture
def mock_storage_service(monkeypatch):
    """Fixture for mocking storage service."""
    mock = AsyncMock()
    monkeypatch.setattr(
        "app.api.endpoints.attachments.get_storage_service", 
        lambda: mock
    )
    return mock


class TestAttachmentEndpoints:
    """Test suite for attachment API endpoints."""
    
    def test_get_attachment_success(self, mock_db_session, mock_storage_service):
        """Test successful attachment retrieval."""
        # Setup
        mock_db, mock_result = mock_db_session
        
        # Create mock attachment
        attachment = MagicMock()
        attachment.id = 1
        attachment.filename = "test.pdf"
        attachment.content_type = "application/pdf"
        attachment.storage_uri = "s3://test-bucket/test.pdf"
        
        mock_result.scalar_one_or_none.return_value = attachment
        mock_storage_service.get_file.return_value = b"test PDF content"
        
        # Execute
        with TestClient(app) as client:
            response = client.get("/attachments/1")
        
        # Verify
        assert response.status_code == status.HTTP_200_OK
        assert response.content == b"test PDF content"
        assert response.headers["Content-Type"] == "application/pdf"
        assert response.headers["Content-Disposition"] == 'attachment; filename="test.pdf"'
        
        # Verify storage service was called
        mock_storage_service.get_file.assert_called_once_with("s3://test-bucket/test.pdf")
    
    def test_get_attachment_not_found(self, mock_db_session, mock_storage_service):
        """Test attachment not found."""
        # Setup
        mock_db, mock_result = mock_db_session
        mock_result.scalar_one_or_none.return_value = None
        
        # Execute
        with TestClient(app) as client:
            response = client.get("/attachments/999")
        
        # Verify
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "Attachment not found" in response.json()["detail"]
    
    def test_get_attachment_content_not_available(self, mock_db_session, mock_storage_service):
        """Test attachment found but content not available."""
        # Setup
        mock_db, mock_result = mock_db_session
        
        # Create mock attachment
        attachment = MagicMock()
        attachment.id = 1
        attachment.filename = "test.pdf"
        attachment.content_type = "application/pdf"
        attachment.storage_uri = "s3://test-bucket/test.pdf"
        
        mock_result.scalar_one_or_none.return_value = attachment
        mock_storage_service.get_file.return_value = None
        
        # Execute
        with TestClient(app) as client:
            response = client.get("/attachments/1")
        
        # Verify
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "Attachment content not available" in response.json()["detail"]
```

### 4. Integration Tests

Create `app/tests/test_integration/test_email_attachment_flow.py`:

```python
import base64
import json
import os
import pytest
from unittest.mock import AsyncMock, patch

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.models.email_data import Attachment, Email
from app.schemas.webhook_schemas import MailchimpWebhook


@pytest.fixture
def sample_webhook_data():
    """Fixture for sample webhook data with attachment."""
    # Load from test data file or create inline
    return {
        "webhook_id": "test-webhook-123",
        "event": "inbound_email",
        "data": {
            "message_id": "test-message-123@mailchimp.com",
            "from_email": "sender@example.com",
            "from_name": "Test Sender",
            "to_email": "receiver@yourdomain.com",
            "subject": "Test email with attachment",
            "body_plain": "This is a test email with attachment",
            "body_html": "<p>This is a test email with attachment</p>",
            "attachments": [
                {
                    "name": "test.pdf",
                    "type": "application/pdf",
                    "content": base64.b64encode(b"PDF test content").decode(),
                    "content_id": None,
                    "size": 15
                }
            ]
        }
    }


class TestEmailAttachmentFlow:
    """Integration tests for the email attachment flow."""
    
    @pytest.mark.asyncio
    async def test_end_to_end_attachment_flow_local(self, sample_webhook_data, tmp_path):
        """Test end-to-end attachment flow with local storage."""
        # Setup
        with patch("app.services.storage_service.settings") as mock_settings, \
             patch("app.db.session.get_db"), \
             patch("app.services.email_processing_service.get_db"):
            
            # Configure for local storage
            mock_settings.USE_S3_STORAGE = False
            mock_settings.ATTACHMENTS_BASE_DIR = tmp_path
            
            # Clear any existing test data
            db = AsyncMock()
            db.execute.return_value.scalar_one_or_none.return_value = None
            
            # Set up database mocks
            with patch("app.db.session.get_db", return_value=db), \
                 patch("app.services.email_processing_service.get_db", return_value=db):
                
                # 1. Process webhook with attachment
                with TestClient(app) as client:
                    response = client.post(
                        "/api/v1/webhooks/mailchimp",
                        json=sample_webhook_data
                    )
                    assert response.status_code == status.HTTP_200_OK
            
                # 2. Verify file was saved to local filesystem
                # Find the saved file in the directory
                saved_files = list(tmp_path.glob("**/test.pdf"))
                assert len(saved_files) == 1
                
                with open(saved_files[0], "rb") as f:
                    assert f.read() == b"PDF test content"
    
    @pytest.mark.asyncio
    async def test_end_to_end_attachment_flow_s3(self, sample_webhook_data):
        """Test end-to-end attachment flow with S3 storage."""
        # Setup
        mock_s3_client = AsyncMock()
        mock_s3_client.__aenter__.return_value = mock_s3_client
        mock_s3_client.put_object = AsyncMock()
        
        mock_stream = AsyncMock()
        mock_stream.__aenter__.return_value = AsyncMock()
        mock_stream.__aenter__.return_value.read = AsyncMock(return_value=b"PDF test content")
        mock_s3_client.get_object = AsyncMock(return_value={"Body": mock_stream})
        
        with patch("app.services.storage_service.settings") as mock_settings, \
             patch("aioboto3.Session") as mock_session:
            
            # Configure for S3 storage
            mock_settings.USE_S3_STORAGE = True
            mock_settings.S3_BUCKET_NAME = "test-bucket"
            mock_session.return_value.client.return_value = mock_s3_client
            
            # Clear any existing test data
            db = AsyncMock()
            db.execute.return_value.scalar_one_or_none.return_value = None
            
            # Create mock for stored attachment
            mock_attachment = AsyncMock()
            mock_attachment.id = 1
            mock_attachment.filename = "test.pdf"
            mock_attachment.content_type = "application/pdf"
            mock_attachment.storage_uri = "s3://test-bucket/attachments/1/abcd1234_test.pdf"
            
            # Set up database mocks for different stages
            with patch("app.db.session.get_db", return_value=db), \
                 patch("app.services.email_processing_service.get_db", return_value=db):
                
                # 1. Process webhook with attachment
                with TestClient(app) as client:
                    response = client.post(
                        "/api/v1/webhooks/mailchimp",
                        json=sample_webhook_data
                    )
                    assert response.status_code == status.HTTP_200_OK
                
                # Verify S3 upload was called
                mock_s3_client.put_object.assert_called_once()
                assert b"PDF test content" in mock_s3_client.put_object.call_args[1]["Body"]
            
            # Set up mock for attachment retrieval
            with patch("app.api.endpoints.attachments.get_db") as mock_get_db, \
                 patch("app.api.endpoints.attachments.get_storage_service") as mock_get_storage:
                
                mock_db = AsyncMock()
                mock_result = AsyncMock()
                mock_result.scalar_one_or_none.return_value = mock_attachment
                mock_db.execute.return_value = mock_result
                mock_get_db.return_value = mock_db
                
                mock_storage = AsyncMock()
                mock_storage.get_file.return_value = b"PDF test content"
                mock_get_storage.return_value = mock_storage
                
                # 2. Retrieve the attachment via API
                with TestClient(app) as client:
                    response = client.get("/attachments/1")
                    assert response.status_code == status.HTTP_200_OK
                    assert response.content == b"PDF test content"
                    assert response.headers["Content-Type"] == "application/pdf"
```

## Migration Strategy for Existing Data

For a production system with existing attachments, add a data migration script:

```python
"""Migration script for transferring existing attachments to S3.

This script migrates attachments from database content column to S3 storage.
Run it after the database schema migration is complete.
"""

import asyncio
import base64
import logging
from typing import List

from sqlalchemy import select

from app.db.session import SessionLocal, engine
from app.models.email_data import Attachment
from app.services.storage_service import StorageService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def migrate_existing_attachments():
    """Migrate all existing attachments to S3 storage."""
    logger.info("Starting attachment migration to S3...")
    
    # Initialize services
    storage = StorageService()
    
    # Use a new session for the migration
    async with SessionLocal() as session:
        # Get all attachments with content data but no storage_uri
        query = select(Attachment).where(
            Attachment.content.is_not(None),
            Attachment.storage_uri.is_(None)
        )
        result = await session.execute(query)
        attachments = result.scalars().all()
        
        logger.info(f"Found {len(attachments)} attachments to migrate")
        
        for i, attachment in enumerate(attachments):
            try:
                # Generate object key
                object_key = f"attachments/{attachment.email_id}/{attachment.id}_{attachment.filename}"
                
                # Upload to storage
                storage_uri = await storage.save_file(
                    file_data=attachment.content,
                    object_key=object_key,
                    content_type=attachment.content_type
                )
                
                # Update the attachment record
                attachment.storage_uri = storage_uri
                
                # Log progress periodically
                if (i + 1) % 10 == 0 or i == len(attachments) - 1:
                    logger.info(f"Migrated {i + 1}/{len(attachments)} attachments")
                
            except Exception as e:
                logger.error(f"Error migrating attachment {attachment.id}: {str(e)}")
                # Continue with next attachment even if one fails
        
        # Commit all changes at once
        await session.commit()
    
    logger.info("Attachment migration completed")


if __name__ == "__main__":
    asyncio.run(migrate_existing_attachments())
```

## Deployment Checklist

Before deploying to Heroku, verify:

1. **All tests pass**:
   ```bash
   pytest -v
   ```

2. **Database migrations are ready**:
   ```bash
   alembic revision --autogenerate -m "Update attachment model to use storage_uri"
   alembic upgrade head
   ```

3. **Heroku environment variables are set**:
   ```bash
   heroku config:set S3_BUCKET_NAME=your-bucket-name
   heroku config:set AWS_ACCESS_KEY_ID=your-access-key
   heroku config:set AWS_SECRET_ACCESS_KEY=your-secret-key
   heroku config:set AWS_REGION=your-region
   heroku config:set USE_S3_STORAGE=true
   ```

4. **Procfile is created**:
   ```
   release: alembic upgrade head
   web: uvicorn app.main:app --host=0.0.0.0 --port=${PORT:-8000}
   ```

5. **S3 bucket is properly configured**:
   - Correct permissions
   - CORS settings if needed
   - Lifecycle policies for cost management

6. **Monitoring is ready**:
   - Set up error alerts
   - Configure logging to capture storage-related errors

7. **Run data migration if needed**:
   ```bash
   python -m app.scripts.migrate_attachments_to_s3
   ```

## Conclusion

This implementation provides a robust solution for handling email attachments when deploying to Heroku. By leveraging Amazon S3 for storage while maintaining compatibility with local filesystem for development, we've created a flexible system that addresses the limitations of both database binary storage and Heroku's ephemeral filesystem.

The TDD approach ensures code quality and proper functioning across different environments, while the clean abstraction in the storage service allows for potential future extensions (such as using other cloud storage providers). 