"""Email dependencies for dependency injection."""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps.database import get_db
from app.api.v1.deps.storage import get_storage_service
from app.core.config import settings
from app.integrations.email.client import WebhookClient
from app.services.attachment_service import AttachmentService
from app.services.email_service import EmailService
from app.services.storage_service import StorageService

__all__ = ["get_webhook_client", "get_attachment_service", "get_email_service"]


def get_webhook_client() -> WebhookClient:
    """Get an instance of the WebhookClient for dependency injection.

    This dependency provides a client for handling email webhook data
    from email providers like Mailchimp/Mandrill.

    Returns:
        WebhookClient: A configured WebhookClient instance with API keys
            and secrets from application settings

    Example:
        ```python
        @app.post("/webhooks/inbound")
        async def handle_webhook(
            request: Request,
            client: WebhookClient = Depends(get_webhook_client)
        ):
            # Parse and validate the webhook data
            webhook_data = await client.parse_webhook(request)

            # Process the validated webhook data
            # ...

            return {"status": "success", "message_id": webhook_data.id}
        ```
    """
    return WebhookClient(
        api_key=settings.MAILCHIMP_API_KEY,
        webhook_secret=settings.MAILCHIMP_WEBHOOK_SECRET,
        server_prefix=None,
    )


async def get_attachment_service(
    db: AsyncSession = Depends(get_db),
    storage: StorageService = Depends(get_storage_service),
) -> AttachmentService:
    """Dependency function to get the attachment service.

    This dependency provides a service for processing email attachments,
    including storing them in the database and/or external storage.

    Args:
        db: Database session for persistence operations
        storage: Storage service for file operations

    Returns:
        AttachmentService: A configured AttachmentService instance

    Example:
        ```python
        @app.post("/attachments")
        async def create_attachment(
            file: UploadFile,
            email_id: int,
            service: AttachmentService = Depends(get_attachment_service)
        ):
            # Process and store the attachment
            attachment_data = {
                "filename": file.filename,
                "content_type": file.content_type,
                "content": await file.read()
            }
            attachment = await service.create_attachment(email_id, attachment_data)
            return attachment
        ```
    """
    return AttachmentService(db=db, storage=storage)


async def get_email_service(
    db: AsyncSession = Depends(get_db),
    attachment_service: AttachmentService = Depends(get_attachment_service),
) -> EmailService:
    """Dependency function to get the email service.

    This dependency provides a service for processing email data,
    including storing emails and their attachments.

    Args:
        db: Database session for persistence operations
        attachment_service: Service for handling email attachments

    Returns:
        EmailService: A configured EmailService instance

    Example:
        ```python
        @app.post("/webhooks/email")
        async def process_email_webhook(
            request: Request,
            webhook_client: WebhookClient = Depends(get_webhook_client),
            email_service: EmailService = Depends(get_email_service)
        ):
            # Parse the webhook data
            webhook_data = await webhook_client.parse_webhook(request)

            # Process the email using the service
            email = await email_service.process_webhook(webhook_data)

            return {"status": "success", "email_id": email.id}
        ```
    """
    return EmailService(db=db, attachment_service=attachment_service)
