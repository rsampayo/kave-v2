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
import time
from typing import Any, Optional, Tuple

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_db, get_email_service, get_webhook_client
from app.api.v1.endpoints.webhooks.mandrill.parsers import (
    _is_empty_event_list,
    _is_ping_event,
    _prepare_webhook_body,
)
from app.api.v1.endpoints.webhooks.mandrill.processors import (
    _handle_event_list,
    _handle_single_event_dict,
)
from app.core.config import settings
from app.integrations.email.client import WebhookClient
from app.models.organization import Organization
from app.schemas.webhook_schemas import WebhookResponse
from app.services.email_service import EmailService

# Set up logging
logger = logging.getLogger(__name__)

# Create API router for Mandrill webhooks
router = APIRouter()

# Create dependencies
get_db_session = Depends(get_db)
get_webhook = Depends(get_webhook_client)
get_email_handler = Depends(get_email_service)


def _get_webhook_signature(request: Request) -> Optional[str]:
    """Extract webhook signature from request headers.

    Args:
        request: The FastAPI request object

    Returns:
        Optional[str]: The signature if present, None otherwise
    """
    signature = request.headers.get("X-Mandrill-Signature") or request.headers.get(
        "X-Mailchimp-Signature"
    )
    logger.info(
        f"Received webhook with signature: {signature[:8]}..."
        if signature
        else "No signature provided"
    )
    return signature


def _get_actual_webhook_url(request: Request) -> str:
    """Get the full request URL for signature verification.

    Args:
        request: The FastAPI request object

    Returns:
        str: The actual webhook URL
    """
    host = request.headers.get("host", "")
    scheme = request.headers.get("x-forwarded-proto", "https")
    path = request.url.path
    actual_webhook_url = f"{scheme}://{host}{path}"
    logger.info(f"Using actual request URL for verification: {actual_webhook_url}")
    return actual_webhook_url


async def _verify_webhook_body(request: Request) -> Tuple[Any, Optional[JSONResponse]]:
    """Verify that we have a valid webhook body to process.

    Args:
        request: The FastAPI request object

    Returns:
        Tuple: (body, error_response)
            - body: The parsed webhook body or None if invalid
            - error_response: JSONResponse with error details or None if valid
    """
    # Prepare the webhook body
    body, error_response = await _prepare_webhook_body(request)

    # Return error response if parsing failed
    if error_response:
        return None, error_response

    # Verify we have a body to process
    if body is None:
        logger.info("Missing webhook body received")
        return None, JSONResponse(
            content={
                "status": "error",
                "message": "No parseable body found",
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return body, None


def _get_verification_body(request: Request, body: Any) -> Any:
    """Determine the best verification body to use.

    Args:
        request: The FastAPI request object
        body: The parsed webhook body

    Returns:
        Any: The verification body to use
    """
    # For form data, prefer the raw form data or mandrill_events directly
    if hasattr(request.state, "raw_form_data"):
        verification_body = request.state.raw_form_data
        logger.info("Using raw form data for signature verification")
    elif hasattr(request.state, "mandrill_events"):
        # If we have the mandrill_events extracted, create a dict with it
        verification_body = {"mandrill_events": request.state.mandrill_events}
        logger.info("Using extracted mandrill_events for signature verification")
    elif hasattr(request.state, "original_body"):
        verification_body = request.state.original_body
        logger.info("Using original unparsed request body for signature verification")
    else:
        verification_body = body
        logger.info("Using parsed body for signature verification")

    return verification_body


async def _verify_organization_signature(
    client: WebhookClient,
    signature: str,
    webhook_url: str,
    verification_body: Any,
    db: AsyncSession,
) -> Tuple[Optional[Organization], bool]:
    """Verify organization by signature.

    Args:
        client: The webhook client
        signature: The webhook signature
        webhook_url: The webhook URL
        verification_body: The verification body
        db: Database session

    Returns:
        Tuple: (organization, is_verified)
            - organization: The organization if found, None otherwise
            - is_verified: True if signature is valid, False otherwise
    """
    # Identify organization by signature
    logger.info("Starting organization identification by signature")
    start_time = time.time()

    organization, is_verified = await client.identify_organization_by_signature(
        signature, webhook_url, verification_body, db
    )

    verification_time = time.time() - start_time
    logger.info(f"Signature verification completed in {verification_time:.3f}s")

    # Log the verification result with environment information
    if is_verified and organization is not None:
        logger.info(
            f"✅ Verified webhook signature for organization: {organization.name} "
            f"in environment: {settings.API_ENV}"
        )
    else:
        logger.warning(
            f"❌ Received webhook with invalid or unknown signature "
            f"in environment: {settings.API_ENV}"
        )

    return organization, is_verified


def _handle_webhook_verification_errors(
    is_verified: bool, signature: Optional[str]
) -> Optional[JSONResponse]:
    """Handle webhook verification errors.

    Args:
        is_verified: True if signature is valid, False otherwise
        signature: The webhook signature

    Returns:
        Optional[JSONResponse]: Error response if verification failed, None otherwise
    """
    # Reject unverified webhooks if configured to do so
    if settings.should_reject_unverified and signature and not is_verified:
        logger.warning(
            f"🛑 Rejecting unverified webhook due to configuration "
            f"in environment: {settings.API_ENV}"
        )
        return JSONResponse(
            content={
                "status": "error",
                "message": "Invalid webhook signature",
            },
            # Return 401 to cause Mailchimp to retry
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    return None


def _handle_special_webhooks(
    body: dict[str, Any] | list[dict[str, Any]],
) -> Optional[JSONResponse]:
    """Handle special webhook types like empty events and ping events.

    Args:
        body: The webhook body

    Returns:
        Optional[JSONResponse]: Response for special webhooks or None for normal processing
    """
    # Check if this is just an empty event array - accept it for testing
    if _is_empty_event_list(body):
        logger.info("Received empty events list - accepting for testing purposes")
        return JSONResponse(
            content={
                "status": "success",
                "message": "Empty events list acknowledged",
            },
            status_code=status.HTTP_200_OK,
        )

    # Check if this is a ping event for webhook validation
    if _is_ping_event(body):
        logger.info("Received webhook validation ping")
        return JSONResponse(
            content={
                "status": "success",
                "message": "Ping acknowledged",
            },
            status_code=status.HTTP_202_ACCEPTED,
        )

    return None


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
        # Extract the signature from headers
        signature = _get_webhook_signature(request)

        # Log all headers for debugging
        headers_dict = dict(request.headers)
        logger.debug(f"Request headers: {headers_dict}")

        # Get the actual webhook URL for verification
        actual_webhook_url = _get_actual_webhook_url(request)

        # Verify webhook body
        body, error_response = await _verify_webhook_body(request)
        if error_response:
            return error_response

        # Log environment information
        logger.info(f"Processing webhook in environment: {settings.API_ENV}")
        logger.debug(
            f"Webhook environment settings: "
            f"PRODUCTION={settings.MAILCHIMP_WEBHOOK_BASE_URL_PRODUCTION}, "
            f"TESTING={settings.MAILCHIMP_WEBHOOK_BASE_URL_TESTING}, "
            f"REJECT_UNVERIFIED_PROD={settings.MAILCHIMP_REJECT_UNVERIFIED_PRODUCTION}, "
            f"REJECT_UNVERIFIED_TEST={settings.MAILCHIMP_REJECT_UNVERIFIED_TESTING}"
        )

        # Validate the webhook signature if provided and get organization
        organization = None
        is_verified = False

        if signature and hasattr(client, "identify_organization_by_signature"):
            # Use the actual received URL, not the configured one
            webhook_url = actual_webhook_url
            logger.info(f"Using actual webhook URL for verification: {webhook_url}")

            # Determine the best verification body to use
            verification_body = _get_verification_body(request, body)

            # Identify organization by signature
            organization, is_verified = await _verify_organization_signature(
                client, signature, webhook_url, verification_body, db
            )
        else:
            if not signature:
                logger.warning("No signature provided in webhook request")
            elif not hasattr(client, "identify_organization_by_signature"):
                logger.error(
                    "WebhookClient does not have identify_organization_by_signature method"
                )

        # Store the organization with the request for use in services
        request.state.organization = organization
        request.state.is_verified = is_verified

        # Handle verification errors
        error_response = _handle_webhook_verification_errors(is_verified, signature)
        if error_response:
            return error_response

        # Handle special webhook types
        special_response = _handle_special_webhooks(body)
        if special_response:
            return special_response

        # Handle based on body type (list or dict)
        if isinstance(body, list):
            return await _handle_event_list(body, client, email_service, request)
        elif isinstance(body, dict):
            return await _handle_single_event_dict(body, client, email_service, request)
        else:
            # For unsupported body types, return a 400 Bad Request
            return JSONResponse(
                content={
                    "status": "error",
                    "message": f"Invalid webhook payload: Unsupported data type {type(body)}",
                },
                status_code=status.HTTP_400_BAD_REQUEST,
            )
    except Exception as e:
        # Log the error for debugging
        logger.error(f"Error processing webhook: {str(e)}")

        # For invalid data, return 400 Bad Request
        if "Invalid webhook payload" in str(e):
            return JSONResponse(
                content={
                    "status": "error",
                    "message": str(e),
                },
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Return 200 OK for other errors as Mandrill expects 2xx responses
        # to avoid retry attempts
        return JSONResponse(
            content={
                "status": "error",
                "message": f"Failed to process webhook but acknowledged: {str(e)}",
            },
            status_code=status.HTTP_202_ACCEPTED,
        )
