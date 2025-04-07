"""Email webhook endpoints module.

Contains FastAPI routes for handling webhook requests from MailChimp.
"""

import logging

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import verify_webhook_signature
from app.db.session import get_db
from app.integrations.email.client import MailchimpClient, mailchimp_client
from app.schemas.webhook_schemas import WebhookResponse
from app.services.email_processing_service import (
    EmailProcessingService,
    get_email_service,
)

# Set up logging
logger = logging.getLogger(__name__)

# Create API router for webhooks
router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# Create instances first to avoid function calls in parameter defaults
email_service_dependency = Depends(get_email_service)
mailchimp_client_instance = Depends(lambda: mailchimp_client)
verify_signature_dependency = Depends(verify_webhook_signature)


@router.post(
    "/mailchimp",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Receive MailChimp email webhook",
    description=(
        "Endpoint for MailChimp to send email data via webhook. "
        "Processes incoming emails, extracts data, "
        "and stores them in the database."
    ),
    response_model=WebhookResponse,
    responses={
        status.HTTP_202_ACCEPTED: {
            "description": "Webhook received and processed successfully",
            "model": WebhookResponse,
            "content": {
                "application/json": {
                    "example": {
                        "status": "success",
                        "message": "Email processed successfully",
                    }
                }
            },
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "An error occurred while processing the webhook",
            "model": WebhookResponse,
            "content": {
                "application/json": {
                    "example": {
                        "status": "error",
                        "message": "Failed to process webhook: Invalid data format",
                    }
                }
            },
        },
    },
)
async def receive_mailchimp_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: bool = verify_signature_dependency,
    email_service: EmailProcessingService = email_service_dependency,
    client: MailchimpClient = mailchimp_client_instance,
) -> JSONResponse:
    """Handle MailChimp email webhook.

    This endpoint receives webhooks from MailChimp containing email data.
    It validates the webhook signature, processes the email content including
    any attachments, and stores the data in the database.

    Args:
        request: The FastAPI request object containing the webhook payload
        db: Database session for persistence operations
        _: Dependency to verify webhook signature (automatically checks auth)
        email_service: Service for processing email data
        client: MailChimp client for webhook parsing

    Returns:
        JSONResponse: Success response with 202 status or error with 500 status

    Raises:
        HTTPException: If signature verification fails
    """
    try:
        # Parse webhook data
        webhook_data = await client.parse_webhook(request)

        # Process the webhook
        await email_service.process_webhook(webhook_data)

        return JSONResponse(
            content={"status": "success", "message": "Email processed successfully"},
            status_code=status.HTTP_202_ACCEPTED,
        )
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        # Note: Returning 500 for internal errors, though Mailchimp might prefer 2xx
        return JSONResponse(
            content={
                "status": "error",
                "message": f"Failed to process webhook: {str(e)}",
            },
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
