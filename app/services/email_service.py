"""Module providing Email Service functionality for the services."""

import logging
from datetime import datetime

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.email_data import Email
from app.schemas.webhook_schemas import InboundEmailData, MailchimpWebhook
from app.services.attachment_service import AttachmentService, get_attachment_service

logger = logging.getLogger(__name__)


class EmailService:
    """Service responsible for processing emails."""

    def __init__(self, db: AsyncSession, attachment_service: AttachmentService):
        """Initialize the email service.

        Args:
            db: Database session
            attachment_service: Service for processing attachments
        """
        self.db = db
        self.attachment_service = attachment_service

    async def process_webhook(self, webhook: MailchimpWebhook) -> Email:
        """Process a webhook containing email data.

        Args:
            webhook: The webhook data

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

            # Process and store any attachments if present
            if webhook.data.attachments:
                await self.attachment_service.process_attachments(
                    email.id, webhook.data.attachments
                )

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

        self.db.add(email)
        # Flush to get the ID (but don't commit yet)
        await self.db.flush()

        return email

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
    attachment_service: AttachmentService = Depends(get_attachment_service),
) -> EmailService:
    """Dependency function to get the email processing service.

    Args:
        db: Database session
        attachment_service: Attachment service

    Returns:
        EmailService: The email service
    """
    return EmailService(db=db, attachment_service=attachment_service)
