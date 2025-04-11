"""Email webhook endpoints module.

Contains FastAPI routes for handling webhook requests from Mandrill.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Tuple, Union

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.integrations.email.client import WebhookClient, get_webhook_client
from app.schemas.webhook_schemas import WebhookResponse
from app.services.email_service import EmailService, get_email_service

# Set up logging
logger = logging.getLogger(__name__)

# Create API router for webhooks
router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# Create dependencies
get_db_session = Depends(get_db)
get_webhook = Depends(get_webhook_client)
get_email_handler = Depends(get_email_service)


def _process_mandrill_headers(headers: Dict[str, Any]) -> Dict[str, str]:
    """Process Mandrill headers to ensure they're all strings.

    Mandrill may send headers as lists of strings, but our schema expects Dict[str, str].
    This function converts any list values to strings by joining them.

    Args:
        headers: The raw headers from Mandrill

    Returns:
        Dict[str, str]: Headers with all values as strings
    """
    processed_headers = {}
    for key, value in headers.items():
        if isinstance(value, list):
            # Join list values with a newline for readability
            processed_headers[key] = "\n".join(value)
        else:
            processed_headers[key] = str(value)
    return processed_headers


async def _handle_form_data(
    request: Request,
) -> Tuple[
    Optional[Union[Dict[str, Any], List[Dict[str, Any]]]], Optional[JSONResponse]
]:
    """Parse and handle form data from a Mandrill webhook request.

    Args:
        request: The FastAPI request object

    Returns:
        Tuple containing:
        - The parsed webhook body (dict or list) or None if parsing failed
        - An error response or None if successful
    """
    try:
        form_data = await request.form()
        # Log that we received form data, without creating an unused variable
        logger.debug(f"Received Mandrill form data with {len(form_data)} fields")

        if "mandrill_events" in form_data:
            # This is the standard Mandrill format
            mandrill_events = form_data["mandrill_events"]

            try:
                # Ensure we have a string before trying to parse as JSON
                mandrill_events_str = (
                    str(mandrill_events)
                    if not isinstance(mandrill_events, (str, bytes, bytearray))
                    else mandrill_events
                )
                body = json.loads(mandrill_events_str)
                logger.debug(
                    f"Successfully parsed Mandrill events JSON. "
                    f"Event count: {len(body) if isinstance(body, list) else 1}"
                )
                return body, None
            except Exception as form_err:
                logger.error(f"Failed to parse mandrill_events: {str(form_err)}")
                return None, JSONResponse(
                    content={
                        "status": "error",
                        "message": f"Invalid Mandrill webhook format: {str(form_err)}",
                    },
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
        else:
            logger.warning("Mandrill form data missing 'mandrill_events' field")
            return None, JSONResponse(
                content={
                    "status": "error",
                    "message": "Missing 'mandrill_events' field in form data",
                },
                status_code=status.HTTP_400_BAD_REQUEST,
            )
    except Exception as form_err:
        logger.error(f"Error processing form data: {str(form_err)}")
        return None, JSONResponse(
            content={
                "status": "error",
                "message": f"Error processing form data: {str(form_err)}",
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )


async def _handle_json_body(
    request: Request,
) -> Tuple[
    Optional[Union[Dict[str, Any], List[Dict[str, Any]]]], Optional[JSONResponse]
]:
    """Parse and handle JSON data from a Mandrill webhook request.

    Args:
        request: The FastAPI request object

    Returns:
        Tuple containing:
        - The parsed webhook body (dict or list) or None if parsing failed
        - An error response or None if successful
    """
    try:
        body = await request.json()
        logger.debug("Successfully parsed JSON body")
        return body, None
    except Exception as json_err:
        logger.error(f"Failed to parse request as JSON: {str(json_err)}")
        return None, JSONResponse(
            content={
                "status": "error",
                "message": f"Unsupported Mandrill webhook format: {str(json_err)}",
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )


def _parse_message_id(headers: Dict[str, Any]) -> str:
    """Extract message ID from headers or generate a fallback.

    Args:
        headers: Email headers dictionary

    Returns:
        str: Extracted or generated message ID
    """
    message_id = ""
    if headers:
        for header_name in [
            "Message-Id",
            "Message-ID",
            "message-id",
            "message_id",
        ]:
            if header_name in headers:
                message_id = headers[header_name]
                # Strip any < > characters that might be around the message ID
                message_id = message_id.strip("<>")
                logger.debug(f"Found message ID in headers: {message_id}")
                break
    return message_id


def _normalize_attachments(
    attachments: Union[List[Dict[str, Any]], Dict[str, Any], str, Any],
) -> List[Dict[str, Any]]:
    """Normalize attachments to ensure they are in the expected format.

    Args:
        attachments: Raw attachments data from Mandrill

    Returns:
        List[Dict[str, Any]]: Normalized attachments list
    """
    # Handle case where attachments might be a string or other non-list/dict type
    if not attachments:
        return []

    if isinstance(attachments, list) and all(
        isinstance(item, dict) for item in attachments
    ):
        logger.debug(f"Email has {len(attachments)} attachments")
        return attachments

    logger.warning(
        f"Unexpected attachments format: {type(attachments).__name__}. "
        f"Converting to proper format."
    )

    # Try to convert to a proper format if it's a string that might be JSON
    if isinstance(attachments, str):
        try:
            parsed_attachments = json.loads(attachments)
            if isinstance(parsed_attachments, list):
                logger.debug(
                    f"Successfully parsed attachments string to list of "
                    f"{len(parsed_attachments)} items"
                )
                return parsed_attachments
            else:
                logger.warning(
                    "Parsed attachments is not a list, creating empty attachments list"
                )
                return []
        except json.JSONDecodeError:
            logger.warning(
                "Could not parse attachments string as JSON, "
                "creating empty attachments list"
            )
            return []
    elif isinstance(attachments, dict):
        # Handle the case where attachments is a dictionary
        logger.debug("Converting attachments from dict to list format")

        # Check if the dict has expected attachment fields
        if "name" in attachments and "type" in attachments:
            # It's likely an attachment dictionary, so wrap it in a list
            return [attachments]
        else:
            # Try to extract attachment info from the dictionary structure
            attachment_list = []
            for _key, value in attachments.items():
                if isinstance(value, dict) and "name" in value and "type" in value:
                    attachment_list.append(value)

            if attachment_list:
                logger.debug(
                    f"Extracted {len(attachment_list)} attachments "
                    f"from dictionary structure"
                )
                return attachment_list
            else:
                logger.warning(
                    "Could not extract attachments from dictionary, "
                    "creating empty attachments list"
                )
                return []
    else:
        logger.warning(
            "Attachments is not a list, string, or dict; "
            "creating empty attachments list"
        )
        return []


def _format_event(
    event: Dict[str, Any], event_index: int, event_type: str, event_id: str
) -> Optional[Dict[str, Any]]:
    """Format a Mandrill event into our standard webhook format.

    Args:
        event: The raw Mandrill event
        event_index: Index of the event in the batch
        event_type: The event type
        event_id: The event ID

    Returns:
        Dict[str, Any]: Formatted event or None if the event can't be processed
    """
    if "msg" not in event:
        logger.warning(
            f"Skipping Mandrill event with no msg field: "
            f"event_type={event_type}, id={event_id}"
        )
        return None

    # Map 'inbound' event type to 'inbound_email' if needed
    if event_type == "inbound":
        event_type = "inbound_email"

    # Extract message data
    msg = event.get("msg", {})
    subject = msg.get("subject", "")[:50]  # Limit long subjects
    from_email = msg.get("from_email", "")
    logger.info(f"Processing email from: {from_email}, Subject: {subject}")

    # Process attachments
    attachments = msg.get("attachments", [])
    normalized_attachments = _normalize_attachments(attachments)

    # Get and process headers to convert any list values to strings
    headers = msg.get("headers", {})
    processed_headers = _process_mandrill_headers(headers)

    # Extract message_id from headers
    message_id = _parse_message_id(headers)

    # If no message ID in headers, fall back to Mandrill's internal ID
    if not message_id:
        message_id = msg.get("_id", "")
        if message_id:
            logger.debug(f"Using Mandrill internal ID: {message_id}")
        else:
            logger.warning("No message ID found in headers or Mandrill data")

    # Format the event for processing
    formatted_event = {
        "event": event_type,
        "webhook_id": event_id,
        "timestamp": event.get("ts", ""),
        "data": {
            "message_id": message_id,
            "from_email": from_email,
            "from_name": msg.get("from_name", ""),
            "to_email": msg.get("email", ""),
            "subject": subject,
            "body_plain": msg.get("text", ""),
            "body_html": msg.get("html", ""),
            "headers": processed_headers,
            "attachments": normalized_attachments,
        },
    }

    return formatted_event


async def _process_single_event(
    client: WebhookClient,
    email_service: EmailService,
    event: Dict[str, Any],
    event_index: int,
) -> bool:
    """Process a single Mandrill event.

    Args:
        client: Webhook client for parsing
        email_service: Email service for processing
        event: The event to process
        event_index: Index of the event in the batch

    Returns:
        bool: True if processing succeeded, False otherwise
    """
    try:
        # Log basic event info for troubleshooting
        event_type = event.get("event", "unknown")
        event_id = event.get("_id", f"unknown_{event_index}")
        logger.info(
            f"Processing Mandrill event {event_index+1}: type={event_type}, id={event_id}"
        )

        # Format the event
        formatted_event = _format_event(event, event_index, event_type, event_id)
        if not formatted_event:
            return False

        # Process the webhook data
        webhook_data = await client.parse_webhook(formatted_event)
        await email_service.process_webhook(webhook_data)
        logger.info(f"Successfully processed Mandrill event {event_index+1}")
        return True
    except Exception as event_err:
        logger.error(
            f"Error processing Mandrill event {event_index+1}: {str(event_err)}"
        )
        return False


async def _process_event_batch(
    client: WebhookClient,
    email_service: EmailService,
    events: List[Dict[str, Any]],
) -> Tuple[int, int]:
    """Process a batch of Mandrill events.

    Args:
        client: Webhook client for parsing
        email_service: Email service for processing
        events: List of events to process

    Returns:
        Tuple[int, int]: Count of processed and skipped events
    """
    event_count = len(events)
    logger.info(f"Processing {event_count} Mandrill events")
    processed_count = 0
    skipped_count = 0

    for event_index, event in enumerate(events):
        success = await _process_single_event(client, email_service, event, event_index)
        if success:
            processed_count += 1
        else:
            skipped_count += 1

    return processed_count, skipped_count


async def _process_non_list_event(
    client: WebhookClient, email_service: EmailService, body: Dict[str, Any]
) -> JSONResponse:
    """Process a single non-list format Mandrill event.

    Args:
        client: Webhook client for parsing
        email_service: Email service for processing
        body: The event body to process

    Returns:
        JSONResponse: Response to return to the client
    """
    logger.warning(
        "Received Mandrill webhook with non-list format, attempting to process"
    )

    # Process headers if present to handle list values
    if isinstance(body, dict) and "data" in body and "headers" in body["data"]:
        body["data"]["headers"] = _process_mandrill_headers(body["data"]["headers"])

    webhook_data = await client.parse_webhook(body)
    await email_service.process_webhook(webhook_data)

    return JSONResponse(
        content={
            "status": "success",
            "message": "Email processed successfully",
        },
        status_code=status.HTTP_202_ACCEPTED,
    )


async def _prepare_webhook_body(
    request: Request,
) -> Tuple[
    Optional[Union[Dict[str, Any], List[Dict[str, Any]]]], Optional[JSONResponse]
]:
    """Extract and prepare the webhook body from a request.

    Args:
        request: The FastAPI request object

    Returns:
        Tuple containing:
        - The parsed webhook body (dict or list) or None if parsing failed
        - An error response or None if successful
    """
    logger.info("======= MANDRILL WEBHOOK RECEIVED =======")

    # Log the content type for debugging
    content_type = request.headers.get("content-type", "")
    logger.debug(f"Webhook received with Content-Type: {content_type}")

    # Get the raw request body for logging
    raw_body = await request.body()
    if not raw_body:
        logger.warning("Empty request body received from Mandrill")
        return None, JSONResponse(
            content={"status": "error", "message": "Empty request body"},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    logger.debug(f"Webhook body size: {len(raw_body)} bytes")

    # Parse the request body based on content type
    if (
        "application/x-www-form-urlencoded" in content_type
        or "multipart/form-data" in content_type
    ):
        logger.debug("Processing webhook as form data")
        return await _handle_form_data(request)
    else:
        # Try parsing as JSON in case Mandrill changes their format
        logger.debug("Attempting to process webhook as direct JSON")
        return await _handle_json_body(request)


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
    email_service: EmailService = get_email_handler,
    client: WebhookClient = get_webhook,
) -> JSONResponse:
    """Handle Mandrill email webhook.

    This endpoint receives webhooks from Mandrill containing email data.
    Mandrill typically sends data as form data with a field named 'mandrill_events'
    containing a JSON string with an array of events.

    Args:
        request: The FastAPI request object containing the webhook payload
        db: Database session for persistence operations
        email_service: Service for processing email data
        client: Webhook client for webhook parsing

    Returns:
        JSONResponse: Success response with appropriate status code:
            - 200 OK for ping events during webhook registration
            - 202 ACCEPTED for regular webhook events
            - 500 INTERNAL SERVER ERROR for processing errors
    """
    try:
        # Prepare the webhook body
        body, error_response = await _prepare_webhook_body(request)

        # Return error response if parsing failed
        if error_response:
            return error_response

        # Verify we have a body to process
        if not body:
            logger.error("No parseable body found in Mandrill webhook")
            return JSONResponse(
                content={"status": "error", "message": "No parseable body found"},
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Check if this is a ping event for webhook validation
        if isinstance(body, dict) and (
            body.get("type") == "ping" or body.get("event") == "ping"
        ):
            logger.info("Received Mandrill webhook validation ping")
            return JSONResponse(
                content={
                    "status": "success",
                    "message": "Webhook validation successful",
                },
                status_code=status.HTTP_200_OK,
            )

        # Handle Mandrill's array-based format (standard format)
        if isinstance(body, list):
            processed_count, skipped_count = await _process_event_batch(
                client, email_service, body
            )

            # Return summary of processing
            if processed_count > 0:
                message = f"Processed {processed_count} events successfully"
                if skipped_count > 0:
                    message += f" ({skipped_count} skipped)"

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
                    status_code=status.HTTP_200_OK,  # Use 200 for Mandrill to avoid retries
                )
        else:
            # Handle non-list format (unusual for Mandrill but handle it anyway)
            return await _process_non_list_event(client, email_service, body)
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
