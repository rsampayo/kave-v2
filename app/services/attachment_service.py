import base64
import logging
import uuid
from typing import List

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.email_data import Attachment
from app.schemas.webhook_schemas import EmailAttachment
from app.services.storage_service import StorageService, get_storage_service

logger = logging.getLogger(__name__)


class AttachmentService:
    """Service responsible for processing and storing email attachments."""

    def __init__(self, db: AsyncSession, storage: StorageService):
        """Initialize the attachment service.

        Args:
            db: Database session
            storage: Storage service for handling attachments
        """
        self.db = db
        self.storage = storage

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

            # Create the attachment model
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
                    content_type=attach_data.type,
                )

                # Update the model with the storage URI
                attachment.storage_uri = storage_uri

            self.db.add(attachment)
            result.append(attachment)

        return result


async def get_attachment_service(
    db: AsyncSession = Depends(get_db),
    storage: StorageService = Depends(get_storage_service),
) -> AttachmentService:
    """Dependency function to get the attachment service.

    Args:
        db: Database session
        storage: Storage service

    Returns:
        AttachmentService: The attachment service
    """
    return AttachmentService(db=db, storage=storage)
