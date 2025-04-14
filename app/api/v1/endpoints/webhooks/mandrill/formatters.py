"""Mandrill webhook formatters module.

Contains functions for formatting webhook events from Mandrill to the application's
standardized format.
"""

import logging
from typing import Any

from app.api.v1.endpoints.webhooks.common.attachments import _normalize_attachments

# Set up logging
logger = logging.getLogger(__name__)


def _process_mandrill_headers(headers: dict[str, Any]) -> dict[str, str]:
    """Process Mandrill headers to ensure they're all strings.

    Mandrill may send headers as lists of strings, but our schema expects Dict[str, str].
    This function converts any list values to strings by joining them.

    Args:
        headers: The raw headers from Mandrill

    Returns:
        Dict[str, str]: Headers with all values as strings
    """
    if headers is None:
        return {}

    processed_headers = {}
    for key, value in headers.items():
        if isinstance(value, list):
            # Join list values with a newline for readability
            processed_headers[key] = "\n".join(value)
        else:
            processed_headers[key] = str(value)
    return processed_headers


def _parse_message_id(headers: dict[str, Any]) -> str:
    """Parse the message ID from headers or generate a fallback.

    Args:
        headers: Dictionary containing message headers

    Returns:
        str: The message ID or empty string if not found
    """
    if headers is None:
        return ""

    # First check for X-Mailgun-Message-Id or X-Message-Id headers
    for header_name in ["X-Mailgun-Message-Id", "X-Message-Id"]:
        if header_name in headers and headers[header_name]:
            return str(headers[header_name]).strip()

    # Next, check for Message-Id or Message-ID
    for header_name in ["Message-Id", "Message-ID", "message-id", "message_id"]:
        if header_name in headers and headers[header_name]:
            message_id = str(headers[header_name]).strip()
            # Some ESPs wrap message IDs in angle brackets; remove if present
            if message_id.startswith("<") and message_id.endswith(">"):
                message_id = message_id[1:-1]
            return message_id

    # Finally, fallback to 'id' field if present, or return empty string
    if "id" in headers and headers["id"]:
        return str(headers["id"]).strip()
    return ""


def _format_event(
    event: dict[str, Any], event_index: int, event_type: str, event_id: str
) -> dict[str, Any] | None:
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
    logger.info("Processing email: %s, Subject: %s", from_email, subject)

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
