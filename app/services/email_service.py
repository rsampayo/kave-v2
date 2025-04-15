"""Module providing Email Service functionality for the services."""

import logging
from datetime import datetime
from typing import Optional

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps.database import get_db
from app.api.v1.deps.storage import get_storage_service
from app.models.email_data import Email, EmailAttachment
from app.models.organization import Organization
from app.schemas.webhook_schemas import EmailAttachment as SchemaEmailAttachment
from app.schemas.webhook_schemas import InboundEmailData, MailchimpWebhook
from app.services.attachment_service import AttachmentService, get_attachment_service
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
    attachments: list[SchemaEmailAttachment],
) -> list[EmailAttachment]:
    """Convert a list of schema attachments to model attachments.

    Args:
        attachments: List of schema attachment objects

    Returns:
        List[EmailAttachment]: List of model attachment objects
    """
    return [_schema_to_model_attachment(attachment) for attachment in attachments]


class EmailService:
    """Service responsible for processing emails and attachments."""

    def __init__(
        self,
        db: AsyncSession,
        attachment_service: AttachmentService,
        storage: StorageService,
    ):
        """Initialize the email service.

        Args:
            db: Database session
            attachment_service: Service for processing attachments
            storage: Storage service for handling file storage
        """
        self.db = db
        self.attachment_service = attachment_service
        self.storage = storage

    async def process_webhook(
        self, webhook: MailchimpWebhook, organization: Optional[Organization] = None
    ) -> Email:
        """Process a webhook containing email data.

        Args:
            webhook: The webhook data
            organization: Optional pre-identified organization (e.g., from signature verification)

        Returns:
            Email: The created email model

        Raises:
            ValueError: If email processing fails
        """
        try:
            # If organization is not provided, try to identify it from the email
            if organization is None:
                organization = await self._identify_organization(webhook.data.to_email)

            # Create the email model
            email = await self.store_email(
                webhook.data, webhook.webhook_id, webhook.event, organization
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

    async def _identify_organization(self, to_email: str) -> Optional[Organization]:
        """Identify the organization based on the recipient's email.

        Args:
            to_email: Email address of the recipient

        Returns:
            Optional[Organization]: The organization if found, None otherwise
        """
        # Try to find the organization by email
        query = select(Organization).where(
            Organization.webhook_email == to_email,
            Organization.is_active == True,  # noqa: E712
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def store_email(
        self,
        email_data: InboundEmailData,
        webhook_id: str,
        event: str,
        organization: Optional[Organization] = None,
    ) -> Email:
        """Store an email in the database.

        Args:
            email_data: The parsed email data
            webhook_id: ID of the webhook
            event: Type of webhook event
            organization: The organization that sent the email (optional)

        Returns:
            Email: The created email model
        """
        # Check if email already exists (by message_id)
        existing_email = await self.get_email_by_message_id(email_data.message_id)
        if existing_email:
            logger.info(
                "Email with message ID %s already exists", email_data.message_id
            )

            # Update organization if needed
            if organization and not existing_email.organization_id:
                existing_email.organization_id = organization.id
                await self.db.flush()

            return existing_email

        # Truncate subject if it's too long (database column limit)
        subject = email_data.subject
        if subject and len(subject) > 255:
            subject = subject[:255]

        # Create a new email
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
            organization_id=organization.id if organization else None,
        )

        self.db.add(email)
        # Flush to get the ID (but don't commit yet)
        await self.db.flush()

        return email

    async def get_email_by_message_id(self, message_id: str) -> Optional[Email]:
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
    storage: StorageService = Depends(get_storage_service),
) -> EmailService:
    """Dependency function to get the email service.

    Args:
        db: Database session
        attachment_service: Attachment service
        storage: Storage service

    Returns:
        EmailService: The email service
    """
    return EmailService(db=db, attachment_service=attachment_service, storage=storage)
