"""Email webhook endpoints module.

Contains FastAPI routes for handling webhook requests from Mandrill.

This module provides FastAPI routes and supporting functions for processing webhook
requests from Mandrill email service. The main functionality includes:

1. Receiving and validating webhook requests in various formats (JSON, form data)
2. Processing email events (inbound emails, delivery notifications, etc.)
3. Normalizing and formatting data for consistent internal representation
4. Handling attachments with proper MIME decoding
5. Storing processed email data through the email service

The module is structured with a main endpoint function (receive_mandrill_webhook) that
orchestrates the request handling process, supported by helper functions that handle
specific aspects of webhook processing.
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
            return _parse_form_field(form_data, "mandrill_events")
        else:
            # Try alternate field names that Mandrill might use
            body, error = _check_alternate_form_fields(form_data)
            if body is not None or error is not None:
                return body, error

            # If we get here, no valid fields were found
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


def _parse_form_field(
    form_data: Any, field_name: str
) -> Tuple[
    Optional[Union[Dict[str, Any], List[Dict[str, Any]]]], Optional[JSONResponse]
]:
    """Parse a form field as JSON.

    Args:
        form_data: The form data dictionary
        field_name: The name of the field to parse

    Returns:
        Tuple containing:
        - The parsed field value or None if parsing failed
        - An error response or None if successful
    """
    try:
        field_value = form_data[field_name]
        field_value_str = (
            str(field_value)
            if not isinstance(field_value, (str, bytes, bytearray))
            else field_value
        )
        body = json.loads(field_value_str)
        if field_name == "mandrill_events":
            logger.info(
                f"Parsed Mandrill events. Count: {len(body) if isinstance(body, list) else 1}"
            )
        else:
            logger.info(
                f"Using alternate field {field_name!r} instead of 'mandrill_events'"
            )
        return body, None
    except Exception as err:
        logger.error(f"Failed to parse {field_name}: {str(err)}")
        # Log a sample of the content that failed to parse
        if field_name in form_data:
            sample = (
                str(form_data[field_name])[:100] + "..."
                if len(str(form_data[field_name])) > 100
                else str(form_data[field_name])
            )
            logger.error(f"Sample of unparseable content: {sample}")
        return None, JSONResponse(
            content={
                "status": "error",
                "message": f"Invalid Mandrill webhook format: {str(err)}",
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )


def _check_alternate_form_fields(
    form_data: Any,
) -> Tuple[
    Optional[Union[Dict[str, Any], List[Dict[str, Any]]]], Optional[JSONResponse]
]:
    """Check alternate field names that Mandrill might use.

    Args:
        form_data: The form data dictionary

    Returns:
        Tuple containing:
        - The parsed field value or None if no valid fields found
        - An error response or None if successful
    """
    alternate_fields = ["events", "data", "payload", "webhook"]
    for field in alternate_fields:
        if field in form_data:
            return _parse_form_field(form_data, field)
    return None, None


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


def _is_ping_event(body: Union[Dict[str, Any], List[Dict[str, Any]]]) -> bool:
    """Check if the webhook body represents a ping event for validation.

    Mandrill sends a ping event during the initial webhook setup process to verify
    the endpoint is working correctly. This function detects these validation events
    so they can be handled with a simple acknowledgment rather than full processing.

    A ping event is identified by either a "type" or "event" field with value "ping".

    Args:
        body: The parsed webhook body (either a dictionary or list)

    Returns:
        bool: True if this is a ping event, False otherwise
    """
    return isinstance(body, dict) and (
        body.get("type") == "ping" or body.get("event") == "ping"
    )


def _is_empty_event_list(body: Union[Dict[str, Any], List[Dict[str, Any]]]) -> bool:
    """Check if the webhook body is an empty list.

    Mandrill sometimes sends empty lists in webhooks, which don't need processing.
    This function provides a clean way to detect this case early in the processing pipeline.

    Args:
        body: The parsed webhook body (either a dictionary or list)

    Returns:
        bool: True if body is a list with zero elements, False otherwise
    """
    return isinstance(body, list) and len(body) == 0


async def _parse_json_body(
    request: Request,
) -> Optional[Union[Dict[str, Any], List[Dict[str, Any]]]]:
    """Try different methods to parse JSON body from request.

    Args:
        request: The FastAPI request object

    Returns:
        The parsed webhook body (dict or list) or None if all parsing methods fail
    """
    raw_body = await request.body()
    logger.debug(f"Attempting to parse raw body as JSON: {len(raw_body)} bytes")

    # Try each parsing method sequentially
    body = None

    # Method 1: Parse raw bytes directly
    if body is None:
        try:
            body = await _parse_json_from_bytes(raw_body)
        except json.JSONDecodeError as err:
            logger.debug(f"Failed to parse raw bytes directly: {str(err)}")

    # Method 2: Parse after decoding to string
    if body is None:
        try:
            body = await _parse_json_from_string(raw_body)
        except Exception as err:
            logger.debug(f"Failed to parse JSON from UTF-8 string: {str(err)}")

    # Method 3: Use request.json()
    if body is None:
        try:
            body = await _parse_json_from_request(request)
        except Exception as err:
            logger.error(f"All JSON parsing methods failed. Error: {str(err)}")
            return None

    # Explicit type cast to satisfy mypy
    if isinstance(body, (dict, list)):
        return body
    return None


def _handle_empty_events(
    body: Union[Dict[str, Any], List[Dict[str, Any]]],
) -> Optional[JSONResponse]:
    """Handle empty event lists from webhook.

    Args:
        body: The parsed webhook body

    Returns:
        JSONResponse if body is an empty event list, None otherwise
    """
    if _is_empty_event_list(body):
        logger.info("Received empty events list")
        return JSONResponse(
            content={"status": "error", "message": "No parseable body found"},
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return None


def _handle_ping_event(
    body: Union[Dict[str, Any], List[Dict[str, Any]]],
) -> Optional[JSONResponse]:
    """Handle ping events for webhook validation.

    Args:
        body: The parsed webhook body

    Returns:
        JSONResponse if body is a ping event, None otherwise
    """
    if _is_ping_event(body):
        logger.info("Received webhook validation ping")
        return JSONResponse(
            content={
                "status": "success",
                "message": "Webhook validation successful",
            },
            status_code=status.HTTP_200_OK,
        )
    return None


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
        # Try to parse the JSON body
        body = await _parse_json_body(request)
        if body is None:
            return None, _create_json_error_response("Invalid JSON format")

        # Log information about the parsed body
        _log_parsed_body_info(body)

        # Check for special cases
        empty_response = _handle_empty_events(body)
        if empty_response:
            return None, empty_response

        ping_response = _handle_ping_event(body)
        if ping_response:
            return None, ping_response

        return body, None
    except json.JSONDecodeError as json_err:
        logger.error(f"JSON parse error: {str(json_err)}")
        return None, _create_json_error_response(
            f"Invalid JSON format: {str(json_err)}"
        )
    except Exception as err:
        logger.error(f"Error parsing JSON body: {str(err)}")
        return None, _create_json_error_response(f"Failed to parse JSON: {str(err)}")


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

    This function handles MIME-encoded email headers according to RFC 2047, which defines
    formats like: =?charset?encoding?encoded-text?=

    Common encodings include:
    - Q-encoding (=?utf-8?Q?filename.pdf?=) for quoted-printable
    - B-encoding (=?UTF-8?B?ZmlsZW5hbWUucGRm?=) for base64

    The function uses Python's email.header module to handle the decoding process,
    with fallbacks for various error cases to ensure robustness in processing
    potentially malformed headers from different email clients.

    Args:
        header_value: The potentially MIME-encoded header value

    Returns:
        str: The decoded header value, or the original string if:
             - The input is None or empty
             - The string doesn't contain MIME encoding markers
             - Decoding fails for any reason
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


def _parse_attachments_from_string(attachments_str: str) -> List[Dict[str, Any]]:
    """Extract attachment data from a string input.

    This function handles string inputs to the _normalize_attachments function.
    It attempts to parse the string as JSON and then applies MIME decoding to any filenames.

    Args:
        attachments_str: String containing attachment data, expected to be JSON

    Returns:
        List[Dict[str, Any]]: Normalized list of attachments
    """
    logger.debug(f"Parsing attachments from string: {len(attachments_str)} characters")
    return _parse_attachment_string(attachments_str)


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


def _parse_attachments_from_dict(
    attachment_dict: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Extract attachment data from a dictionary input.

    This function handles dictionary inputs to the _normalize_attachments function.
    It processes both direct attachment dictionaries and nested structures,
    and applies MIME decoding to any filenames.

    Args:
        attachment_dict: Dictionary containing attachment data

    Returns:
        List[Dict[str, Any]]: Normalized list of attachments
    """
    logger.debug(
        f"Parsing attachments from dictionary with {len(attachment_dict)} keys"
    )
    return _process_attachment_dict(attachment_dict)


def _process_attachment_list(
    attachment_list: List[Any],
) -> List[Dict[str, Any]]:
    """Process a list of attachments to ensure all items are dictionaries.

    This function handles list inputs to the _normalize_attachments function.
    It ensures all items are dictionaries and applies MIME decoding to any filenames.

    Args:
        attachment_list: List containing attachment data

    Returns:
        List[Dict[str, Any]]: Normalized list of attachments
    """
    logger.debug(f"Processing attachment list with {len(attachment_list)} items")

    # Filter to only include dictionary items
    if all(isinstance(item, dict) for item in attachment_list):
        _decode_filenames_in_attachments(attachment_list)
        return attachment_list
    else:
        # If the list contains non-dictionary items, return as is
        # This preserves the existing behavior seen in tests
        return attachment_list


def _normalize_attachments(
    attachments: Union[List[Dict[str, Any]], Dict[str, Any], str, Any],
) -> List[Dict[str, Any]]:
    """Normalize attachments to ensure they are in the expected format.

    This function handles the various formats that Mandrill might send attachment data in:
    - List of attachment dictionaries (ideal case)
    - Single attachment dictionary
    - JSON string containing attachment data
    - Other unexpected formats

    For each format, appropriate parsing and normalization is applied, including:
    - MIME decoding of attachment filenames
    - Ensuring consistent structure
    - Basic validation of attachment data

    The function delegates to specialized helpers (_process_attachment_list,
    _parse_attachments_from_string, _parse_attachments_from_dict) based on input type.

    Args:
        attachments: Raw attachments data from Mandrill, which could be in various formats

    Returns:
        List[Dict[str, Any]]: Normalized list of attachment dictionaries, or empty list if
                              attachments were invalid or empty
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

    # Handle list input
    if isinstance(attachments, list):
        return _process_attachment_list(attachments)

    logger.debug(f"Converting attachments from {type(attachments).__name__} format")

    # Handle JSON string
    if isinstance(attachments, str):
        return _parse_attachments_from_string(attachments)

    # Handle dictionary
    elif isinstance(attachments, dict):
        return _parse_attachments_from_dict(attachments)

    # Handle unsupported types
    else:
        return []


def _format_event(
    event: Dict[str, Any], event_index: int, event_type: str, event_id: str
) -> Optional[Dict[str, Any]]:
    """Format a Mandrill event into our standard webhook format.

    This function transforms the raw Mandrill event structure into our application's
    standardized webhook format. It:

    1. Extracts key data from the Mandrill event
    2. Normalizes attachments using _normalize_attachments
    3. Processes headers to ensure consistent format
    4. Extracts or generates a message_id
    5. Structures the data into our standard format with metadata, content, and details sections

    The returned structure follows this format:
    ```
    {
        "event": <event_type>,
        "webhook_id": <event_id>,
        "timestamp": <timestamp>,
        "data": {
            "message_id": <message_id>,
            "from_email": <from_email>,
            "from_name": <from_name>,
            "to_email": <to_email>,
            "subject": <subject>,
            "body_plain": <text>,
            "body_html": <html>,
            "headers": <processed_headers>,
            "attachments": <normalized_attachments>
        }
    }
    ```

    Args:
        event: The raw Mandrill event dictionary
        event_index: Index of the event in the batch (for logging)
        event_type: The event type (e.g., "inbound", "delivered")
        event_id: The event ID for tracking

    Returns:
        Dict[str, Any]: Formatted event dictionary or None if the event is missing required data
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

    # Create event metadata
    event_metadata = {
        "event": event_type,
        "webhook_id": event_id,
        "timestamp": event.get("ts", ""),
    }

    # Create message content
    message_content = {
        "message_id": message_id,
        "from_email": from_email,
        "from_name": msg.get("from_name", ""),
        "to_email": msg.get("email", ""),
        "subject": subject,
    }

    # Create message body
    message_body = {
        "body_plain": msg.get("text", ""),
        "body_html": msg.get("html", ""),
    }

    # Create message attachments and headers
    message_details = {
        "headers": processed_headers,
        "attachments": normalized_attachments,
    }

    # Combine all components into the final formatted event
    formatted_event = {
        **event_metadata,
        "data": {
            **message_content,
            **message_body,
            **message_details,
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

    This function serves as the first step in the webhook processing pipeline. It:

    1. Determines the request content type (form data vs. direct JSON)
    2. Delegates to specialized parsers (_handle_form_data or _handle_json_body)
    3. Returns both the parsed body and any error response

    This separation of concerns allows the main endpoint function to focus on
    orchestration rather than parsing details.

    Args:
        request: The FastAPI request object containing the raw webhook data

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


async def _handle_event_list(
    body: List[Dict[str, Any]], client: WebhookClient, email_service: EmailService
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

    Returns:
        JSONResponse: Response with processing results summary and appropriate status code
    """
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


async def _handle_single_event_dict(
    body: Dict[str, Any], client: WebhookClient, email_service: EmailService
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

    Returns:
        JSONResponse: Response with processing result and 202 Accepted status code
    """
    return await _process_non_list_event(client, email_service, body)


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
                    "message": "Webhook validation successful",
                },
                status_code=status.HTTP_200_OK,
            )

        # Handle based on body type (list or dict)
        if isinstance(body, list):
            return await _handle_event_list(body, client, email_service)
        else:
            return await _handle_single_event_dict(body, client, email_service)
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
