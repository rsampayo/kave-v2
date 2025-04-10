"""Email webhook endpoints module.

Contains FastAPI routes for handling webhook requests from MailChimp.
"""

import logging

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import verify_webhook_signature
from app.db.session import get_db
from app.integrations.email.client import MailchimpClient, get_mailchimp_client
from app.schemas.webhook_schemas import WebhookResponse
from app.services.email_service import EmailService, get_email_service

# Set up logging
logger = logging.getLogger(__name__)

# Create API router for webhooks
router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# Create dependencies
verify_signature = Depends(verify_webhook_signature)
get_db_session = Depends(get_db)
get_mailchimp = Depends(get_mailchimp_client)
get_email_handler = Depends(get_email_service)


@router.head(
    "/mailchimp",
    status_code=status.HTTP_200_OK,
    summary="Handle MailChimp webhook validation (HEAD request)",
    description=(
        "MailChimp sends a HEAD request to validate the webhook URL "
        "before sending POST data. "
        "This endpoint acknowledges the HEAD request."
    ),
    include_in_schema=False,  # Hide from OpenAPI docs as it's for validation
)
async def head_mailchimp_webhook() -> None:
    """Acknowledge MailChimp's HEAD request for webhook validation."""
    return None


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
    db: AsyncSession = get_db_session,
    _: bool = verify_signature,
    email_service: EmailService = get_email_handler,
    client: MailchimpClient = get_mailchimp,
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
        JSONResponse: Success response with appropriate status code:
            - 200 OK for ping events during webhook registration
            - 202 ACCEPTED for regular webhook events
            - 500 INTERNAL SERVER ERROR for processing errors

    Raises:
        HTTPException: If parsing fails
    """
    try:
        # First try to get the raw request body as text to validate it's not empty
        raw_body = await request.body()
        if not raw_body:
            return JSONResponse(
                content={"status": "error", "message": "Empty request body"},
                status_code=status.HTTP_400_BAD_REQUEST,
            )
            
        # Log the raw body for debugging
        logger.debug(f"Raw Mailchimp webhook body: {raw_body}")
        
        # Try to parse the JSON body
        try:
            body = await request.json()
        except Exception as json_err:
            logger.error(f"Failed to parse Mailchimp webhook JSON: {str(json_err)}")
            return JSONResponse(
                content={
                    "status": "error", 
                    "message": f"Invalid JSON format: {str(json_err)}"
                },
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Check if this is a ping event for webhook validation
        if body.get("type") == "ping" or body.get("event") == "ping":
            logger.info("Received Mailchimp webhook validation ping")
            return JSONResponse(
                content={
                    "status": "success",
                    "message": "Webhook validation successful",
                },
                status_code=status.HTTP_200_OK,
            )

        # Parse webhook data for regular events
        # Pass the already parsed body to avoid parsing it twice
        webhook_data = await client.parse_webhook(body)

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


@router.post(
    "/mandrill",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Receive Mandrill email webhook",
    description=(
        "Endpoint for Mandrill to send email data via webhook. "
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
async def receive_mandrill_webhook(
    request: Request,
    db: AsyncSession = get_db_session,
    _: bool = verify_signature,
    email_service: EmailService = get_email_handler,
    client: MailchimpClient = get_mailchimp,
) -> JSONResponse:
    """Handle Mandrill email webhook.

    This endpoint receives webhooks from Mandrill containing email data.
    It validates the webhook signature, processes the email content including
    any attachments, and stores the data in the database.

    Mandrill webhook format may differ from Mailchimp, with events wrapped in a 'mandrill_events' field.

    Args:
        request: The FastAPI request object containing the webhook payload
        db: Database session for persistence operations
        _: Dependency to verify webhook signature (automatically checks auth)
        email_service: Service for processing email data
        client: MailChimp client for webhook parsing

    Returns:
        JSONResponse: Success response with appropriate status code:
            - 200 OK for ping events during webhook registration
            - 202 ACCEPTED for regular webhook events
            - 500 INTERNAL SERVER ERROR for processing errors
    """
    try:
        # First try to get the raw request body as text
        raw_body = await request.body()
        if not raw_body:
            return JSONResponse(
                content={"status": "error", "message": "Empty request body"},
                status_code=status.HTTP_400_BAD_REQUEST,
            )
            
        # Log the raw body for debugging
        logger.debug(f"Raw Mandrill webhook body: {raw_body}")
        
        try:
            # Try to parse the JSON
            body = await request.json()
        except Exception as json_err:
            logger.error(f"Failed to parse Mandrill webhook JSON: {str(json_err)}")
            # Try to handle form data if JSON parsing fails
            form_data = await request.form()
            if "mandrill_events" in form_data:
                # Mandrill sends events in a form field called 'mandrill_events'
                import json
                try:
                    body = json.loads(form_data["mandrill_events"])
                except Exception as form_err:
                    logger.error(f"Failed to parse mandrill_events: {str(form_err)}")
                    return JSONResponse(
                        content={
                            "status": "error", 
                            "message": f"Invalid Mandrill webhook format: {str(form_err)}"
                        },
                        status_code=status.HTTP_400_BAD_REQUEST,
                    )
            else:
                return JSONResponse(
                    content={
                        "status": "error", 
                        "message": f"Unsupported Mandrill webhook format: {str(json_err)}"
                    },
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

        # Check if this is a ping event for webhook validation
        if isinstance(body, dict) and (body.get("type") == "ping" or body.get("event") == "ping"):
            logger.info("Received Mandrill webhook validation ping")
            return JSONResponse(
                content={
                    "status": "success",
                    "message": "Webhook validation successful",
                },
                status_code=status.HTTP_200_OK,
            )
            
        # Handle Mandrill's array-based format if needed
        if isinstance(body, list):
            # Mandrill might send an array of events
            logger.info(f"Processing {len(body)} Mandrill events")
            processed_count = 0
            
            for event in body:
                # Process each event
                try:
                    # Format the event to match what our parse_webhook expects
                    if "msg" in event:
                        # Mandrill typically has 'msg' containing the email data
                        formatted_event = {
                            "event": event.get("event", "inbound_email"),
                            "webhook_id": event.get("_id", f"mandrill_{processed_count}"),
                            "timestamp": event.get("ts", ""),
                            "data": {
                                "message_id": event.get("msg", {}).get("_id", ""),
                                "from_email": event.get("msg", {}).get("from_email", ""),
                                "from_name": event.get("msg", {}).get("from_name", ""),
                                "to_email": event.get("msg", {}).get("email", ""),
                                "subject": event.get("msg", {}).get("subject", ""),
                                "body_plain": event.get("msg", {}).get("text", ""),
                                "body_html": event.get("msg", {}).get("html", ""),
                                "headers": event.get("msg", {}).get("headers", {}),
                                "attachments": event.get("msg", {}).get("attachments", []),
                            }
                        }
                        
                        webhook_data = await client.parse_webhook(formatted_event)
                        await email_service.process_webhook(webhook_data)
                        processed_count += 1
                    else:
                        logger.warning(f"Skipping Mandrill event with no msg field: {event}")
                        
                except Exception as event_err:
                    logger.error(f"Error processing Mandrill event {processed_count}: {str(event_err)}")
            
            return JSONResponse(
                content={
                    "status": "success", 
                    "message": f"Processed {processed_count} events successfully"
                },
                status_code=status.HTTP_202_ACCEPTED,
            )
        else:
            # Regular webhook format, similar to Mailchimp
            webhook_data = await client.parse_webhook(body)
            await email_service.process_webhook(webhook_data)
            
            return JSONResponse(
                content={
                    "status": "success", 
                    "message": "Email processed successfully"
                },
                status_code=status.HTTP_202_ACCEPTED,
            )
    except Exception as e:
        logger.error(f"Error processing Mandrill webhook: {str(e)}")
        # Return 200 OK even for errors as Mandrill expects 2xx responses
        # to avoid retry attempts
        return JSONResponse(
            content={
                "status": "error",
                "message": f"Failed to process webhook but acknowledged: {str(e)}",
            },
            status_code=status.HTTP_200_OK,
        )
