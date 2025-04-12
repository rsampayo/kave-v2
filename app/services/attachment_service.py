"""Module providing Attachment Service functionality for the services."""

import base64
import email.header
import logging
import mimetypes
import uuid

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

# Fix circular import by importing directly from specific modules
from app.api.deps.database import get_db
from app.api.deps.storage import get_storage_service
from app.models.email_data import Attachment
from app.schemas.webhook_schemas import EmailAttachment
from app.services.storage_service import StorageService

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
        self, email_id: int, attachments: list[EmailAttachment]
    ) -> list[Attachment]:
        """Process and store email attachments.

        Args:
            email_id: ID of the parent email
            attachments: List of attachment data from the webhook

        Returns:
            List[Attachment]: The created attachment models
        """
        result = []

        for attach_data in attachments:
            # Get filename and decode any MIME encoded filename
            original_filename = attach_data.name
            filename = self._decode_mime_header(original_filename)
            if original_filename != filename:
                logger.info(
                    f"Decoded MIME filename from {original_filename!r} to {filename!r}"
                )

            unique_id = str(uuid.uuid4())[:8]
            object_key = f"attachments/{email_id}/{unique_id}_{filename}"

            # Determine proper content type - enhance content type detection
            original_content_type = attach_data.type
            content_type = original_content_type

            if content_type == "application/octet-stream" or not content_type:
                # Try to get a better content type based on file extension
                guessed_type, _ = mimetypes.guess_type(filename)
                if guessed_type:
                    content_type = guessed_type
                    logger.info(
                        f"Improved content type from {original_content_type!r} to {content_type!r} "
                        f"for {filename!r}"
                    )

            # Special handling for PDF files
            if filename.lower().endswith(".pdf") and content_type != "application/pdf":
                content_type = "application/pdf"
                logger.info(
                    f"Setting content type to 'application/pdf' for {filename!r} "
                    f"(was: {original_content_type!r})"
                )

            # Create the attachment model
            attachment = Attachment(
                email_id=email_id,
                filename=filename,
                content_type=content_type,
                content_id=attach_data.content_id,
                size=attach_data.size,
                # Leave storage_uri empty initially
            )

            # If attachment has content, decode and save it
            if attach_data.content:
                # Check if base64 flag is set and is False, otherwise assume it's base64 encoded
                is_base64 = getattr(attach_data, "base64", True)

                if is_base64:
                    # Decode base64 content
                    content = base64.b64decode(attach_data.content)
                else:
                    # Content is already binary data
                    content = (
                        attach_data.content.encode("utf-8")
                        if isinstance(attach_data.content, str)
                        else attach_data.content
                    )

                # Log details about the attachment content
                logger.info(
                    f"Processing attachment {filename!r}: base64={is_base64}, "
                    f"size={len(content)} bytes, content_type={content_type!r}, "
                    f"storage_key={object_key!r}"
                )

                # Save to storage service (S3 or filesystem based on settings)
                storage_uri = await self.storage.save_file(
                    file_data=content,
                    object_key=object_key,
                    content_type=content_type,
                )

                # Update the model with the storage URI
                attachment.storage_uri = storage_uri

            self.db.add(attachment)
            result.append(attachment)

        return result

    def _decode_mime_header(self, header_value: str) -> str:
        """Decode a MIME-encoded header value.

        This handles headers encoded with formats like:
        =?utf-8?Q?filename.pdf?=

        Args:
            header_value: The MIME-encoded header value

        Returns:
            str: The decoded header value
        """
        if not header_value or "=?" not in header_value:
            return header_value

        try:
            # email.header.decode_header returns a list of (decoded_string, charset) tuples
            decoded_parts = email.header.decode_header(header_value)

            # Join the parts together
            result = ""
            for part, charset in decoded_parts:
                if isinstance(part, bytes) and charset:
                    result += part.decode(charset, errors="replace")
                elif isinstance(part, bytes):
                    result += part.decode("utf-8", errors="replace")
                else:
                    result += str(part)

            return result
        except Exception as e:
            logger.warning("Failed to decode MIME header: %s", str(e))
            return header_value


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
