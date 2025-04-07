import base64
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.email_data import Attachment, Email, EmailAttachment
from app.schemas.webhook_schemas import EmailAttachment as SchemaEmailAttachment
from app.schemas.webhook_schemas import InboundEmailData, MailchimpWebhook

logger = logging.getLogger(__name__)

# Directory to store attachments
ATTACHMENTS_DIR = Path("data/attachments")


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
    return EmailAttachment(
        name=schema_attachment.name,
        type=schema_attachment.type,
        content=schema_attachment.content or "",
        content_id=schema_attachment.content_id,
        size=schema_attachment.size,
    )


def _schema_to_model_attachments(
    schema_attachments: List[SchemaEmailAttachment],
) -> List[EmailAttachment]:
    """Convert list of schema attachments to model attachments.

    Args:
        schema_attachments: List of schema attachment objects

    Returns:
        List[EmailAttachment]: List of model attachment objects
    """
    return [_schema_to_model_attachment(a) for a in schema_attachments]


class EmailProcessingService:
    """Service responsible for processing emails and attachments."""

    def __init__(self, db: AsyncSession):
        """Initialize the email processing service.

        Args:
            db: Database session
        """
        self.db = db

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
            logger.error(f"Failed to process webhook: {str(e)}")
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
            logger.info(f"Email with message ID {email_data.message_id} already exists")
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

        self.db.add(email)
        # Flush to get the ID (but don't commit yet)
        await self.db.flush()

        return email

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

        # Ensure attachments directory exists
        os.makedirs(ATTACHMENTS_DIR, exist_ok=True)

        for attach_data in attachments:
            # Create path for storing the attachment with a unique identifier
            filename = attach_data.name
            unique_id = str(uuid.uuid4())[:8]  # Use first 8 chars of UUID for brevity
            file_path = ATTACHMENTS_DIR / f"{email_id}_{unique_id}_{filename}"

            # Create the attachment model
            attachment = Attachment(
                email_id=email_id,
                filename=filename,
                content_type=attach_data.type,
                content_id=attach_data.content_id,
                size=attach_data.size,
                file_path=str(file_path),
            )

            # If attachment has content, decode and save it
            if attach_data.content:
                # Decode base64 content
                content = base64.b64decode(attach_data.content)
                attachment.content = content

                # Save to file system
                with open(file_path, "wb") as f:
                    f.write(content)

            self.db.add(attachment)
            result.append(attachment)

        return result

    async def get_email_by_message_id(self, message_id: str) -> Optional[Email]:
        """Get an email by its message ID.

        Args:
            message_id: The unique message ID

        Returns:
            Optional[Email]: The email if found, None otherwise
        """
        query = select(Email).where(Email.message_id == message_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()


async def get_email_service(
    db: AsyncSession = Depends(get_db),
) -> EmailProcessingService:
    """Dependency function to get the email processing service.

    Args:
        db: Database session

    Returns:
        EmailProcessingService: The email processing service
    """
    return EmailProcessingService(db)
