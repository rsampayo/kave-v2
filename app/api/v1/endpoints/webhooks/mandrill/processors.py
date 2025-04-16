"""Mandrill webhook processors module.

Contains functions for processing webhook events from Mandrill.
"""

import logging
from typing import Any

from fastapi import Request, status
from fastapi.responses import JSONResponse

from app.api.v1.endpoints.webhooks.mandrill.formatters import (
    _format_event,
    _process_mandrill_headers,
)
from app.integrations.email.client import WebhookClient
from app.services.email_service import EmailService

# Set up logging
logger = logging.getLogger(__name__)


async def _process_single_event(
    client: WebhookClient,
    email_service: EmailService,
    event: dict[str, Any],
    event_index: int,
    request: Request | None = None,
) -> bool:
    """Process a single Mandrill event.

    Args:
        client: Webhook client for parsing
        email_service: Email service for processing
        event: The event to process
        event_index: Index of the event in the batch
        request: Optional request object containing state

    Returns:
        bool: True if processing succeeded, False otherwise
    """
    try:
        # Log basic event info for troubleshooting
        event_type = event.get("event", "unknown")
        event_id = event.get("_id", f"unknown_{event_index}")
        logger.debug(
            f"Processing event {event_index + 1}: type={event_type}, id={event_id}"
        )

        # Format the event
        formatted_event = _format_event(event, event_index, event_type, event_id)
        if not formatted_event:
            return False

        # Get organization from request state if available
        organization = None
        is_verified = False

        if request and hasattr(request.state, "organization"):
            organization = request.state.organization
            is_verified = getattr(request.state, "is_verified", False)

            if organization:
                org_name = getattr(organization, "name", "Unknown")
                logger.info(
                    f"Using organization from signature verification: {org_name} "
                    f"(ID: {organization.id}, Verified: {is_verified})"
                )
            else:
                logger.debug(
                    "No organization from signature verification, will attempt to identify from email"
                )

        # Process the webhook data with organization context
        webhook_data = await client.parse_webhook(formatted_event)

        # Log the email being processed
        to_email = (
            webhook_data.data.to_email if hasattr(webhook_data, "data") else "unknown"
        )
        from_email = (
            webhook_data.data.from_email if hasattr(webhook_data, "data") else "unknown"
        )
        subject = (
            webhook_data.data.subject if hasattr(webhook_data, "data") else "unknown"
        )

        logger.info(
            f"Processing email: from={from_email}, to={to_email}, subject={subject}, "
            f"organization={organization.name if organization else 'Unknown'}"
        )

        # Process the webhook
        email = await email_service.process_webhook(
            webhook_data, organization=organization
        )

        logger.info(f"Successfully processed email ID: {email.id}")
        return True
    except Exception as event_err:
        logger.error("Error processing event %s: %s", event_index + 1, str(event_err))
        return False


async def _process_event_batch(
    client: WebhookClient,
    email_service: EmailService,
    events: list[dict[str, Any]],
    request: Request | None = None,
) -> tuple[int, int]:
    """Process a batch of Mandrill events.

    Args:
        client: Webhook client for parsing
        email_service: Email service for processing
        events: List of events to process
        request: Optional request object containing state

    Returns:
        Tuple[int, int]: Count of processed and skipped events
    """
    event_count = len(events)
    logger.info("Processing %s Mandrill events", event_count)
    processed_count = 0
    skipped_count = 0

    for event_index, event in enumerate(events):
        success = await _process_single_event(
            client, email_service, event, event_index, request
        )
        if success:
            processed_count += 1
        else:
            skipped_count += 1

    return processed_count, skipped_count


async def _process_non_list_event(
    client: WebhookClient,
    email_service: EmailService,
    body: dict[str, Any],
    request: Request | None = None,
) -> JSONResponse:
    """Process a single non-list format Mandrill event.

    Args:
        client: Webhook client for parsing
        email_service: Email service for processing
        body: The event body to process
        request: Optional request object containing state

    Returns:
        JSONResponse: Response to return to the client
    """
    logger.warning(
        "Received Mandrill webhook with non-list format, attempting to process"
    )

    # Process headers if present to handle list values
    if isinstance(body, dict) and "data" in body and "headers" in body["data"]:
        body["data"]["headers"] = _process_mandrill_headers(body["data"]["headers"])

    # Get organization from request state if available
    organization = None
    if request and hasattr(request.state, "organization"):
        organization = request.state.organization

    webhook_data = await client.parse_webhook(body)
    await email_service.process_webhook(webhook_data, organization=organization)

    return JSONResponse(
        content={
            "status": "success",
            "message": "Email processed successfully",
        },
        status_code=status.HTTP_202_ACCEPTED,
    )


async def _handle_event_list(
    body: list[dict[str, Any]],
    client: WebhookClient,
    email_service: EmailService,
    request: Request | None = None,
) -> JSONResponse:
    """Handle processing for a list of Mandrill events.

    This function processes a batch of Mandrill events by:

    1. Delegating to _process_event_batch for parallel processing of all events
    2. Tracking the count of successfully processed and skipped events
    3. Generating an appropriate response with summary information

    It maintains Mandrill's expectation of receiving a 200-level response
    even if some events failed to process, to prevent unnecessary retries.

    Args:
        body: List of event dictionaries
        client: Webhook client for parsing events
        email_service: Email service for database operations
        request: Optional request object containing state

    Returns:
        JSONResponse: Response with processing results summary and appropriate status code
    """
    processed_count, skipped_count = await _process_event_batch(
        client, email_service, body, request
    )

    # Return summary of processing
    if processed_count > 0:
        message = f"Processed {processed_count} events successfully"
        if skipped_count > 0:
            message = f"{message} ({skipped_count} skipped)"

        return JSONResponse(
            content={"status": "success", "message": message},
            status_code=status.HTTP_202_ACCEPTED,
        )
    else:
        return JSONResponse(
            content={
                "status": "error",
                "message": f"Failed to process any events ({skipped_count} skipped)",
            },
            status_code=status.HTTP_202_ACCEPTED,
        )


async def _handle_single_event_dict(
    body: dict[str, Any],
    client: WebhookClient,
    email_service: EmailService,
    request: Request | None = None,
) -> JSONResponse:
    """Handle processing for a single Mandrill event in dictionary format.

    This function processes a single Mandrill event that was received as a
    dictionary rather than within an array. This is an uncommon but supported format.

    The function delegates to _process_non_list_event which handles the actual processing
    and returns an appropriate response.

    Args:
        body: Event dictionary to process
        client: Webhook client for parsing the event
        email_service: Email service for database operations
        request: Optional request object containing state

    Returns:
        JSONResponse: Response with processing result and 202 Accepted status code
    """
    return await _process_non_list_event(client, email_service, body, request)


def _is_ping_event(body: dict[str, Any]) -> bool:
    # Implement the logic to determine if the event is a ping event
    # This is a placeholder and should be replaced with the actual implementation
    return False


async def _handle_special_webhooks(
    body: dict[str, Any],
    client: WebhookClient,
    email_service: EmailService,
    request: Request | None = None,
) -> JSONResponse:
    """Handle processing for special webhook events.

    Args:
        body: The event body to process
        client: Webhook client for parsing
        email_service: Email service for processing
        request: Optional request object containing state

    Returns:
        JSONResponse: Response to return to the client
    """
    if _is_ping_event(body):
        logger.info("Received webhook validation ping")
        return JSONResponse(
            content={
                "status": "success",
                "message": "Ping acknowledged",
            },
            status_code=status.HTTP_202_ACCEPTED,
        )
    else:
        return await _process_non_list_event(client, email_service, body, request)
