"""Module providing Email Processing Service functionality for the services."""

import base64
import logging
import mimetypes
import uuid
from datetime import datetime

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_db, get_storage_service
from app.models.email_data import Attachment, Email, EmailAttachment
from app.schemas.webhook_schemas import EmailAttachment as SchemaEmailAttachment
from app.schemas.webhook_schemas import InboundEmailData, MailchimpWebhook
from app.services.storage_service import StorageService

logger = logging.getLogger(__name__)


# Adapter functions to convert between schema and model types
def _schema_to_model_attachment(
    schema_attachment: SchemaEmailAttachment,
) -> EmailAttachment:
    """Convert schema EmailAttachment to model EmailAttachment.

    Args:
        schema_attachment: Schema attachment object

    Returns:
        EmailAttachment: Model attachment object
    """
    # Ensure base64 is always a boolean by using True as default when None
    base64_value = (
        True if schema_attachment.base64 is None else schema_attachment.base64
    )

    return EmailAttachment(
        name=schema_attachment.name,
        type=schema_attachment.type,
        content=schema_attachment.content or "",
        content_id=schema_attachment.content_id,
        size=schema_attachment.size,
        base64=base64_value,
    )


def _schema_to_model_attachments(
    schema_attachments: list[SchemaEmailAttachment],
) -> list[EmailAttachment]:
    """Convert list of schema attachments to model attachments.

    Args:
        schema_attachments: List of schema attachment objects

    Returns:
        List[EmailAttachment]: List of model attachment objects
    """
    return [_schema_to_model_attachment(a) for a in schema_attachments]


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

    async def process_webhook(self, webhook: MailchimpWebhook) -> Email:
        """Process a webhook containing email data.

        Args:
            webhook: The MailChimp webhook data

        Returns:
            Email: The created email model

        Raises:
            ValueError: If email processing fails
        """
        try:
            # Create the email model
            email = await self.store_email(
                webhook.data, webhook.webhook_id, webhook.event
            )

            # Process and store any attachments
            if webhook.data.attachments:
                model_attachments = _schema_to_model_attachments(
                    webhook.data.attachments
                )
                await self.process_attachments(email.id, model_attachments)

            await self.db.commit()
            return email
        except Exception as e:
            await self.db.rollback()
            logger.error("Failed to process webhook: %s", str(e))
            raise ValueError(f"Email processing failed: {str(e)}") from e

    async def store_email(
        self, email_data: InboundEmailData, webhook_id: str, event: str
    ) -> Email:
        """Store an email in the database.

        Args:
            email_data: The parsed email data
            webhook_id: ID of the webhook
            event: Type of webhook event

        Returns:
            Email: The created email model
        """
        # Check if email already exists (by message_id)
        existing_email = await self.get_email_by_message_id(email_data.message_id)
        if existing_email:
            logger.info(
                "Email with message ID %s already exists", email_data.message_id
            )
            return existing_email

        # Truncate subject if it's too long (database column limit)
        subject = email_data.subject
        if subject and len(subject) > 255:
            subject = subject[:255]

        # Create new email
        email = Email(
            message_id=email_data.message_id,
            from_email=email_data.from_email,
            from_name=email_data.from_name,
            to_email=email_data.to_email,
            subject=subject,
            body_text=email_data.body_plain,
            body_html=email_data.body_html,
            webhook_id=webhook_id,
            webhook_event=event,
            received_at=datetime.utcnow(),
        )

        self.db.add(email)  # This is synchronous in SQLAlchemy 2.0+
        # Flush to get the ID (but don't commit yet)
        await self.db.flush()

        return email

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
            # Get filename and generate a unique object key
            filename = attach_data.name
            unique_id = str(uuid.uuid4())[:8]
            object_key = f"attachments/{email_id}/{unique_id}_{filename}"

            # Determine proper content type - enhance content type detection
            original_content_type = attach_data.type
            content_type = original_content_type

            logger.info(
                f"Processing attachment: filename={filename!r}, "
                f"original_content_type={original_content_type!r}"
            )

            if content_type == "application/octet-stream" or not content_type:
                # Try to get a better content type based on file extension
                guessed_type, _ = mimetypes.guess_type(filename)
                if guessed_type:
                    content_type = guessed_type
                    logger.info(
                        f"Improved content type from {original_content_type!r} to {content_type!r} "
                        f"for {filename!r} using mimetypes.guess_type()"
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
                    f"Saving attachment: filename={filename!r}, size={len(content)} bytes, "
                    f"content_type={content_type!r}, storage_key={object_key!r}"
                )

                # Save to storage service (S3 or filesystem based on settings)
                storage_uri = await self.storage.save_file(
                    file_data=content,
                    object_key=object_key,
                    content_type=content_type,
                )

                # Update the model with the storage URI
                attachment.storage_uri = storage_uri

                # No longer store content in the database as it's redundant
                # and can cause database bloat with large attachments

            self.db.add(attachment)  # This is synchronous in SQLAlchemy 2.0+
            result.append(attachment)

        return result

    async def get_email_by_message_id(self, message_id: str) -> Email | None:
        """Get an email by its message ID.

        Args:
            message_id: The unique message ID

        Returns:
            Optional[Email]: The email or None if not found
        """
        query = select(Email).where(Email.message_id == message_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()


async def get_email_service(
    db: AsyncSession = Depends(get_db),
    storage: StorageService = Depends(get_storage_service),
) -> EmailProcessingService:
    """Dependency function to get the email processing service.

    Args:
        db: Database session
        storage: Storage service

    Returns:
        EmailProcessingService: The email processing service
    """
    return EmailProcessingService(db, storage)
