"""Email webhook endpoints module.

Contains FastAPI routes for handling webhook requests from Mandrill.
"""

import email.header  # Add this import for MIME header decoding
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
        logger.debug(f"Received Mandrill form data with {len(form_data)} keys")

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
                logger.info(
                    f"Parsed Mandrill events. Count: {len(body) if isinstance(body, list) else 1}"
                )
                return body, None
            except Exception as form_err:
                logger.error(f"Failed to parse mandrill_events: {str(form_err)}")
                # Log a sample of the content that failed to parse
                sample = (
                    str(mandrill_events)[:100] + "..."
                    if len(str(mandrill_events)) > 100
                    else str(mandrill_events)
                )
                logger.error(f"Sample of unparseable content: {sample}")
                return None, JSONResponse(
                    content={
                        "status": "error",
                        "message": f"Invalid Mandrill webhook format: {str(form_err)}",
                    },
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
        else:
            # Try alternate field names that Mandrill might use
            alternate_fields = ["events", "data", "payload", "webhook"]
            for field in alternate_fields:
                if field in form_data:
                    logger.info(
                        f"Using alternate field {field!r} instead of 'mandrill_events'"
                    )
                    try:
                        field_value = form_data[field]
                        field_value_str = (
                            str(field_value)
                            if not isinstance(field_value, (str, bytes))
                            else field_value
                        )
                        body = json.loads(field_value_str)
                        return body, None
                    except Exception as alt_err:
                        logger.error(
                            f"Failed to parse alternate field {field!r}: {str(alt_err)}"
                        )

            logger.warning("Missing 'mandrill_events' field in form data")
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


async def _parse_json_from_bytes(raw_body: bytes) -> Any:
    """Attempt to parse JSON directly from raw bytes.

    Args:
        raw_body: Raw request body bytes

    Returns:
        The parsed JSON data

    Raises:
        json.JSONDecodeError: If parsing fails
    """
    body = json.loads(raw_body)
    logger.debug("Parsed raw bytes as JSON directly")
    return body


async def _parse_json_from_string(raw_body: bytes) -> Any:
    """Attempt to parse JSON by first decoding bytes to string.

    Args:
        raw_body: Raw request body bytes

    Returns:
        The parsed JSON data

    Raises:
        Exception: If decoding or parsing fails
    """
    string_body = raw_body.decode("utf-8")
    body = json.loads(string_body)
    logger.debug("Parsed JSON from UTF-8 string")
    return body


async def _parse_json_from_request(request: Request) -> Any:
    """Attempt to parse JSON using request.json() method.

    Args:
        request: FastAPI request object

    Returns:
        The parsed JSON data

    Raises:
        Exception: If parsing fails
    """
    body = await request.json()
    logger.debug("Parsed JSON using request.json() method")
    return body


def _log_parsed_body_info(body: Any) -> None:
    """Log information about the parsed body.

    Args:
        body: The parsed JSON body
    """
    if isinstance(body, list):
        logger.debug(f"Parsed JSON body: list with {len(body)} items")
    elif isinstance(body, dict):
        logger.debug(f"Parsed JSON body: dict with {len(body.keys())} keys")
    else:
        logger.debug(f"Parsed JSON body: {type(body).__name__}")


def _create_json_error_response(error_message: str) -> JSONResponse:
    """Create a JSON error response.

    Args:
        error_message: The error message

    Returns:
        JSONResponse: The error response
    """
    return JSONResponse(
        content={
            "status": "error",
            "message": error_message,
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
        # Try to reread the body for JSON parsing
        # This is needed because request.body() might have been called already
        raw_body = await request.body()
        logger.debug(f"Attempting to parse raw body as JSON: {len(raw_body)} bytes")

        # Try multiple parsing strategies in sequence
        try:
            body = await _parse_json_from_bytes(raw_body)
        except json.JSONDecodeError:
            try:
                body = await _parse_json_from_string(raw_body)
            except Exception as decode_err:
                logger.error(f"Failed to decode and parse body: {str(decode_err)}")
                try:
                    body = await _parse_json_from_request(request)
                except Exception as json_err:
                    logger.error(
                        f"Failed to parse using request.json(): {str(json_err)}"
                    )
                    raise decode_err

        # Log information about the parsed body
        _log_parsed_body_info(body)

        return body, None
    except json.JSONDecodeError as json_err:
        logger.error(f"JSON parsing error: {str(json_err)}")
        # Attempt to log a sample of what we tried to parse
        try:
            sample = raw_body.decode("utf-8", errors="replace")[:100]
            logger.error(f"Sample of unparseable JSON content: {sample}...")
        except Exception:
            logger.error("Could not decode body to show sample")

        error_message = f"Invalid JSON format: {str(json_err)}"
        return None, _create_json_error_response(error_message)
    except Exception as json_err:
        logger.error(f"Failed to parse request as JSON: {str(json_err)}")

        error_message = f"Unsupported Mandrill webhook format: {str(json_err)}"
        return None, _create_json_error_response(error_message)


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


def _decode_mime_header(header_value: str) -> str:
    """Decode a MIME-encoded header value.

    This handles headers encoded with formats like:
    =?utf-8?Q?filename.pdf?=

    Args:
        header_value: The MIME-encoded header value

    Returns:
        str: The decoded header value
    """
    if not header_value or "=?" not in header_value:
        return header_value

    try:
        # email.header.decode_header returns a list of (decoded_string, charset) tuples
        decoded_parts = email.header.decode_header(header_value)

        # Join the parts together
        result = ""
        for part, charset in decoded_parts:
            if isinstance(part, bytes) and charset:
                result += part.decode(charset, errors="replace")
            elif isinstance(part, bytes):
                result += part.decode("utf-8", errors="replace")
            else:
                result += str(part)

        return result
    except Exception as e:
        logger.warning(f"Failed to decode MIME header: {str(e)}")
        return header_value


def _decode_filenames_in_attachments(attachments: List[Dict[str, Any]]) -> None:
    """Decode MIME-encoded filenames in a list of attachment dictionaries.

    Args:
        attachments: List of attachment dictionaries to process
    """
    for attachment in attachments:
        if "name" in attachment and attachment["name"]:
            original_name = attachment["name"]
            attachment["name"] = _decode_mime_header(attachment["name"])
            if original_name != attachment["name"]:
                logger.info(
                    f"Decoded MIME filename from {original_name!r} to {attachment['name']!r}, "
                    f"content_type={attachment.get('type', 'N/A')!r}"
                )


def _parse_attachment_string(attachments_str: str) -> List[Dict[str, Any]]:
    """Parse a JSON string to get attachment data.

    Args:
        attachments_str: JSON string with attachment data

    Returns:
        List[Dict[str, Any]]: List of parsed attachments or empty list on error
    """
    try:
        parsed_attachments = json.loads(attachments_str)
        if isinstance(parsed_attachments, list):
            _decode_filenames_in_attachments(parsed_attachments)
            return parsed_attachments
        return []
    except json.JSONDecodeError:
        return []


def _process_attachment_dict(attachment_dict: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Process a dictionary that may contain attachment data.

    Args:
        attachment_dict: Dictionary possibly containing attachment information

    Returns:
        List[Dict[str, Any]]: Normalized list of attachments
    """
    # Check if the dict directly represents an attachment
    if "name" in attachment_dict and "type" in attachment_dict:
        if attachment_dict["name"]:
            attachment_dict["name"] = _decode_mime_header(attachment_dict["name"])
        return [attachment_dict]

    # Try to extract attachment info from nested structure
    attachment_list = []
    for _key, value in attachment_dict.items():
        if isinstance(value, dict) and "name" in value and "type" in value:
            if value["name"]:
                value["name"] = _decode_mime_header(value["name"])
            attachment_list.append(value)

    return attachment_list


def _normalize_attachments(
    attachments: Union[List[Dict[str, Any]], Dict[str, Any], str, Any],
) -> List[Dict[str, Any]]:
    """Normalize attachments to ensure they are in the expected format.

    Args:
        attachments: Raw attachments data from Mandrill

    Returns:
        List[Dict[str, Any]]: Normalized attachments list
    """
    # Log the raw attachment data for debugging
    logger.debug(f"Raw attachments data type: {type(attachments).__name__}")
    if isinstance(attachments, list) and len(attachments) > 0:
        logger.debug(f"Number of attachments: {len(attachments)}")
        # Log the content types of the first few attachments
        for i, att in enumerate(
            attachments[:3]
        ):  # Log only first 3 to avoid excessive logging
            if isinstance(att, dict):
                logger.debug(
                    f"Attachment {i+1} details: "
                    f"name={att.get('name', 'N/A')!r}, "
                    f"type={att.get('type', 'N/A')!r}"
                )

    # Handle case where attachments might be a string or other non-list/dict type
    if not attachments:
        return []

    # Handle list of dictionaries (normal case)
    if isinstance(attachments, list) and all(
        isinstance(item, dict) for item in attachments
    ):
        _decode_filenames_in_attachments(attachments)
        return attachments

    logger.debug(f"Converting attachments from {type(attachments).__name__} format")

    # Handle JSON string
    if isinstance(attachments, str):
        return _parse_attachment_string(attachments)

    # Handle dictionary
    elif isinstance(attachments, dict):
        return _process_attachment_dict(attachments)

    # Handle unsupported types
    else:
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
            f"Skipping event with no msg field: type={event_type}, id={event_id}"
        )
        return None

    # Map 'inbound' event type to 'inbound_email' if needed
    if event_type == "inbound":
        event_type = "inbound_email"

    # Extract message data
    msg = event.get("msg", {})
    subject = msg.get("subject", "")[:50]  # Limit long subjects
    from_email = msg.get("from_email", "")
    logger.info(f"Processing email: {from_email}, Subject: {subject}")

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
        if not message_id:
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
        logger.debug(
            f"Processing event {event_index+1}: type={event_type}, id={event_id}"
        )

        # Format the event
        formatted_event = _format_event(event, event_index, event_type, event_id)
        if not formatted_event:
            return False

        # Process the webhook data
        webhook_data = await client.parse_webhook(formatted_event)
        await email_service.process_webhook(webhook_data)
        return True
    except Exception as event_err:
        logger.error(f"Error processing event {event_index+1}: {str(event_err)}")
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
    logger.info("Mandrill webhook received")

    # Log the content type for debugging
    content_type = request.headers.get("content-type", "")
    logger.debug(f"Content-Type: {content_type}")

    # Get the raw request body
    raw_body = await request.body()
    if not raw_body:
        logger.warning("Empty request body received")
        return None, JSONResponse(
            content={"status": "error", "message": "Empty request body"},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # Parse the request body based on content type
    if (
        "application/x-www-form-urlencoded" in content_type
        or "multipart/form-data" in content_type
    ):
        logger.debug("Processing as form data")
        return await _handle_form_data(request)
    else:
        logger.debug("Processing as direct JSON")
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
            logger.info("Empty webhook body received")
            return JSONResponse(
                content={
                    "status": "error",
                    "message": "No parseable body found",
                },
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Check if this is just an empty event array
        if isinstance(body, list) and len(body) == 0:
            logger.info("Received empty events list")
            return JSONResponse(
                content={"status": "error", "message": "No parseable body found"},
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Check if this is a ping event for webhook validation
        is_ping = isinstance(body, dict) and (
            body.get("type") == "ping" or body.get("event") == "ping"
        )
        if is_ping:
            logger.info("Received webhook validation ping")
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
                    status_code=status.HTTP_200_OK,  # Use 200 for Mandrill to avoid retries
                )
        else:
            # Handle non-list format (unusual for Mandrill but handle it anyway)
            return await _process_non_list_event(client, email_service, body)
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        # Return 200 OK even for errors as Mandrill expects 2xx responses
        # to avoid retry attempts
        return JSONResponse(
            content={
                "status": "error",
                "message": f"Failed to process webhook but acknowledged: {str(e)}",
            },
            status_code=status.HTTP_200_OK,
        )
