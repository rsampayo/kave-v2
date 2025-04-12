"""Mandrill webhook router module.

Contains FastAPI routes for handling webhook requests from Mandrill.

This module provides FastAPI routes for processing webhook requests from
Mandrill email service. The main functionality includes:

1. Receiving and validating webhook requests in various formats (JSON, form data)
2. Processing email events (inbound emails, delivery notifications, etc.)
3. Handling special cases like ping events for webhook validation
4. Delegating to specialized handlers based on payload format
"""

import logging

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.endpoints.webhooks.mandrill.parsers import (
    _is_empty_event_list,
    _is_ping_event,
    _prepare_webhook_body,
)
from app.api.endpoints.webhooks.mandrill.processors import (
    _handle_event_list,
    _handle_single_event_dict,
)
from app.db.session import get_db
from app.integrations.email.client import WebhookClient, get_webhook_client
from app.schemas.webhook_schemas import WebhookResponse
from app.services.email_service import EmailService, get_email_service

# Set up logging
logger = logging.getLogger(__name__)

# Create API router for Mandrill webhooks
router = APIRouter()

# Create dependencies
get_db_session = Depends(get_db)
get_webhook = Depends(get_webhook_client)
get_email_handler = Depends(get_email_service)


@router.post(
    "",
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
    email_service: EmailService = get_email_handler,
    client: WebhookClient = get_webhook,
) -> JSONResponse:
    """Handle Mandrill email webhook requests.

    This endpoint serves as the main entry point for receiving webhook data from Mandrill.
    It orchestrates the complete webhook processing flow:
    1. Parses and validates the incoming request (both JSON and form-encoded formats)
    2. Handles special cases like ping events for webhook validation
    3. Processes event data (single events or batches)
    4. Delegates to specialized handlers based on payload format
    5. Returns appropriate responses with status information

    Mandrill typically sends data in one of these formats:
    - Form data with a 'mandrill_events' field containing a JSON string array of events
    - Direct JSON body with an array of event objects
    - Direct JSON body with a single event object
    - Simple ping object for webhook validation

    Args:
        request: The FastAPI request object containing the webhook payload
        db: Database session for persistence operations
        email_service: Service for processing email data
        client: Webhook client for webhook parsing

    Returns:
        JSONResponse: Response with appropriate status code:
            - 200 OK for ping events or when returning errors (to prevent Mandrill retries)
            - 202 ACCEPTED for successfully processed webhook events
            - 400 BAD REQUEST for parsing/validation errors
    """
    try:
        # Prepare the webhook body
        body, error_response = await _prepare_webhook_body(request)

        # Return error response if parsing failed
        if error_response:
            return error_response

        # Verify we have a body to process
        if not body:
            logger.info("Empty webhook body received")
            return JSONResponse(
                content={
                    "status": "error",
                    "message": "No parseable body found",
                },
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Check if this is just an empty event array
        if _is_empty_event_list(body):
            logger.info("Received empty events list")
            return JSONResponse(
                content={"status": "error", "message": "No parseable body found"},
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Check if this is a ping event for webhook validation
        if _is_ping_event(body):
            logger.info("Received webhook validation ping")
            return JSONResponse(
                content={
                    "status": "success",
                    "message": "Ping acknowledged",
                },
                status_code=status.HTTP_200_OK,
            )

        # Handle based on body type (list or dict)
        if isinstance(body, list):
            return await _handle_event_list(body, client, email_service)
        return await _handle_single_event_dict(body, client, email_service)
    except Exception as e:
        # Log the error for debugging
        logger.error("Error processing webhook: %s", str(e))

        # Return 200 OK even for errors as Mandrill expects 2xx responses
        # to avoid retry attempts
        return JSONResponse(
            content={
                "status": "error",
                "message": f"Failed to process webhook but acknowledged: {str(e)}",
            },
            status_code=status.HTTP_200_OK,
        )
