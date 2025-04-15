"""Mandrill webhook parsers module.

Contains functions for parsing and validating webhook events from Mandrill.
This module handles the extraction and validation of webhook data from various formats
that Mandrill might send, including JSON and form-encoded requests.

Key capabilities:
1. Parse webhook payloads from multiple formats (JSON body, form data)
2. Handle special event types (ping events, empty events)
3. Validate webhook structure and content
4. Create appropriate responses for various parsing scenarios
5. Extract and normalize event data to prepare for processing

All functions are prefixed with underscore as they are intended for internal use within
the Mandrill webhook processing system.
"""

import json
import logging
from typing import Any

from fastapi import Request, status
from fastapi.responses import JSONResponse

# Set up logging
logger = logging.getLogger(__name__)


async def _handle_form_data(
    request: Request,
) -> tuple[dict[str, Any] | list[dict[str, Any]] | None, JSONResponse | None]:
    """Handle form data from Mandrill webhook requests.

    Args:
        request: The FastAPI request object

    Returns:
        Tuple containing:
        - The parsed webhook body (dict or list) or None if parsing failed
        - An error response or None if successful
    """
    try:
        # Log raw body first - with hex dump for byte-level inspection
        raw_body = await request.body()

        # Use safe methods to decode and convert bytes to avoid coroutine issues with mocks
        try:
            raw_body_str = (
                raw_body.decode("utf-8", errors="replace")
                if hasattr(raw_body, "decode")
                else str(raw_body)
            )
            raw_body_hex = (
                raw_body.hex() if hasattr(raw_body, "hex") else repr(raw_body)
            )
            raw_body_repr = repr(raw_body)

            logger.info(
                f"RAW WEBHOOK BODY (length {len(raw_body)} bytes): {raw_body_str}"
            )
            logger.info(f"RAW WEBHOOK BODY (hex): {raw_body_hex}")
            logger.info(f"RAW WEBHOOK BODY (repr): {raw_body_repr}")
        except Exception as decode_err:
            logger.error(f"Error decoding raw body: {str(decode_err)}")

        # Try to URL decode manually to verify
        import urllib.parse

        try:
            # Safely decode the raw_body
            if hasattr(raw_body, "decode"):
                body_str = raw_body.decode("utf-8")
                url_decoded = urllib.parse.unquote(body_str)
                logger.info(f"URL DECODED MANUALLY: {url_decoded}")
        except Exception as e:
            logger.error(f"Manual URL decoding failed: {str(e)}")

        form_data = await request.form()
        logger.info(f"FORM KEYS: {list(form_data.keys())}")
        logger.debug("Received Mandrill form data with %s keys", len(form_data))

        # Dump all form data for debugging with more detail
        for key, value in form_data.items():
            logger.info(
                f"FORM KEY: {key}, VALUE TYPE: {type(value)}, VALUE: {str(value)[:200]}..."
            )
            logger.info(f"FORM VALUE REPR: {repr(value)[:200]}...")

        if "mandrill_events" in form_data:
            # This is the standard Mandrill format
            logger.info("Found 'mandrill_events' field, attempting to parse")
            return _parse_form_field(form_data, "mandrill_events")
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
        logger.error("Error processing form data: %s", str(form_err))
        import traceback

        logger.error(f"Form data processing traceback: {traceback.format_exc()}")
        return None, JSONResponse(
            content={
                "status": "error",
                "message": f"Error processing form data: {str(form_err)}",
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )


def _parse_form_field(
    form_data: Any, field_name: str
) -> tuple[dict[str, Any] | list[dict[str, Any]] | None, JSONResponse | None]:
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
        logger.info(f"Form field value type before conversion: {type(field_value)}")
        logger.info(f"Form field value dir: {dir(field_value)}")

        # If it's a special form data type, check its methods and content
        if hasattr(field_value, "content_type"):
            logger.info(f"Content type: {field_value.content_type}")
        if hasattr(field_value, "filename"):
            logger.info(f"Filename: {field_value.filename}")
        if hasattr(field_value, "read"):
            try:
                content = field_value.read()
                logger.info(f"Content from read(): {content}")
            except Exception as e:
                logger.error(f"Error reading content: {str(e)}")

        field_value_str = (
            str(field_value)
            if not isinstance(field_value, (str, bytes, bytearray))
            else field_value
        )
        logger.info(f"Field value after conversion to string: {repr(field_value_str)}")

        # Try to manually parse as JSON for debugging
        try:
            import json

            # Clean the string first to help with debugging
            cleaned_value = field_value_str.strip()
            logger.info(f"Cleaned value: {repr(cleaned_value)}")
            # Directly parse to confirm if it's valid JSON
            direct_parsed = json.loads(cleaned_value)
            logger.info(f"Direct JSON parsing result: {repr(direct_parsed)}")
        except Exception as e:
            logger.error(f"Manual JSON parsing attempt failed: {str(e)}")

        body = json.loads(field_value_str)
        if field_name == "mandrill_events":
            logger.info(
                f"Parsed Mandrill events. Count: {len(body) if isinstance(body, list) else 1}"
            )
            logger.info(f"Parsed body type: {type(body)}, content: {repr(body)}")
        else:
            logger.info(
                f"Using alternate field {field_name!r} instead of 'mandrill_events'"
            )
        return body, None
    except Exception as err:
        logger.error("Failed to parse %s: %s", field_name, str(err))
        import traceback

        logger.error(f"JSON parsing traceback: {traceback.format_exc()}")
        # Log a sample of the content that failed to parse
        if field_name in form_data:
            sample = (
                str(form_data[field_name])[:100] + "..."
                if len(str(form_data[field_name])) > 100
                else str(form_data[field_name])
            )
            logger.error("Sample of unparseable content: %s", sample)
        return None, JSONResponse(
            content={
                "status": "error",
                "message": f"Invalid Mandrill webhook format: {str(err)}",
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )


def _check_alternate_form_fields(
    form_data: Any,
) -> tuple[dict[str, Any] | list[dict[str, Any]] | None, JSONResponse | None]:
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
        logger.debug("Parsed JSON body: list with %s items", len(body))
    elif isinstance(body, dict):
        logger.debug("Parsed JSON body: dict with %s keys", len(body.keys()))
    else:
        logger.debug("Parsed JSON body of type: %s", type(body))


def _create_json_error_response(error_message: str) -> JSONResponse:
    """Create a JSON error response.

    Args:
        error_message: Error message to include in the response

    Returns:
        A JSONResponse with error status and message
    """
    return JSONResponse(
        content={
            "status": "error",
            "message": f"Failed to process webhook: {error_message}",
        },
        status_code=status.HTTP_400_BAD_REQUEST,
    )


async def _parse_json_body(
    request: Request,
) -> tuple[dict[str, Any] | list[dict[str, Any]] | None, JSONResponse | None]:
    """Parse the JSON body from a request.

    This function attempts multiple strategies to parse the JSON body
    from a FastAPI request.

    Args:
        request: The FastAPI request object

    Returns:
        Tuple containing:
        - The parsed JSON body or None if parsing failed
        - An error response or None if successful
    """
    try:
        # First try the cleaner request.json() method
        body = await _parse_json_from_request(request)
        return body, None
    except Exception as request_json_err:
        # Log the specific error
        logger.warning("Failed to parse with request.json(): %s", str(request_json_err))

        # Fall back to reading the raw body
        try:
            raw_body = await request.body()
            logger.info(f"Raw body length: {len(raw_body)} bytes")

            # Try parsing the raw body as JSON directly
            try:
                body = await _parse_json_from_bytes(raw_body)
                return body, None
            except json.JSONDecodeError as bytes_err:
                logger.warning("Failed to parse bytes directly: %s", str(bytes_err))
                # Sample for debugging
                sample_bytes = raw_body[:100] if len(raw_body) > 100 else raw_body
                logger.info(f"Sample raw bytes: {sample_bytes!r}")

                # Try decoding the bytes to a string first
                try:
                    body = await _parse_json_from_string(raw_body)
                    return body, None
                except Exception as string_err:
                    logger.warning("Failed to parse from string: %s", str(string_err))
                    # Try to see what the string looks like
                    try:
                        sample_string = raw_body.decode("utf-8", errors="replace")[:100]
                        logger.info(f"Sample string from bytes: {sample_string}")
                    except Exception as decode_err:
                        logger.warning(
                            "Failed to decode bytes to string: %s", str(decode_err)
                        )

        except Exception as body_err:
            logger.error("Failed to read request body: %s", str(body_err))

        # If all parsing methods failed, return an error
        error_message = f"Invalid JSON format: {str(request_json_err)}"
        logger.error("All JSON parsing methods failed: %s", error_message)
        return None, _create_json_error_response(error_message)


async def _handle_json_body(
    request: Request,
) -> tuple[dict[str, Any] | list[dict[str, Any]] | None, JSONResponse | None]:
    """Parse and handle a JSON body from a Mandrill webhook request.

    Args:
        request: The FastAPI request object

    Returns:
        Tuple containing:
        - The parsed webhook body (dict or list) or None if parsing failed
        - An error response or None if successful
    """
    try:
        body, error_response = await _parse_json_body(request)
        if error_response:
            return None, error_response

        # Validate that the body is correctly formatted
        if not isinstance(body, (dict, list)):
            logger.warning("Expected dict or list, got %s", type(body))
            return None, JSONResponse(
                content={
                    "status": "error",
                    "message": (
                        f"Invalid Mandrill webhook format but acknowledged: "
                        f"expected object or array, got {type(body).__name__}"
                    ),
                },
                status_code=status.HTTP_200_OK,
            )

        return body, None
    except Exception as json_err:
        logger.error("Error processing JSON body: %s", str(json_err))
        return None, JSONResponse(
            content={
                "status": "error",
                "message": f"Failed to process webhook but acknowledged: {str(json_err)}",
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )


def _is_ping_event(body: dict[str, Any] | list[dict[str, Any]]) -> bool:
    """Check if the request is a ping event.

    Args:
        body: The parsed webhook body

    Returns:
        True if it's a ping event, False otherwise
    """
    if isinstance(body, dict):
        return body.get("type") == "ping" or body.get("event") == "ping"
    if isinstance(body, list) and body:
        first_event = body[0]
        if isinstance(first_event, dict):
            return (
                first_event.get("type") == "ping" or first_event.get("event") == "ping"
            )
    return False


def _is_empty_event_list(body: dict[str, Any] | list[dict[str, Any]]) -> bool:
    """Check if the request body is an empty event list.

    Args:
        body: The parsed webhook body

    Returns:
        True if it's an empty list, False otherwise
    """
    if isinstance(body, list):
        return len(body) == 0
    return False


def _handle_empty_events(
    body: dict[str, Any] | list[dict[str, Any]],
) -> JSONResponse | None:
    """Handle case when the body is an empty list of events.

    Args:
        body: The parsed webhook body

    Returns:
        A response to send, or None to continue processing
    """
    if _is_empty_event_list(body):
        logger.info("Received empty event list from Mandrill")
        # Return a success response for empty event lists
        # This allows Mandrill to test webhooks with empty payloads
        return JSONResponse(
            content={
                "status": "success",
                "message": "Acknowledged empty event list",
            },
            status_code=status.HTTP_200_OK,
        )
    return None


def _handle_ping_event(
    body: dict[str, Any] | list[dict[str, Any]],
) -> JSONResponse | None:
    """Handle ping event from Mandrill.

    Args:
        body: The parsed webhook body

    Returns:
        A response to send, or None to continue processing
    """
    if _is_ping_event(body):
        logger.info("Received ping event from Mandrill")
        return JSONResponse(
            content={
                "status": "success",
                "message": "Ping acknowledged",
            },
            status_code=status.HTTP_200_OK,
        )
    return None


async def _prepare_webhook_body(
    request: Request,
) -> tuple[dict[str, Any] | list[dict[str, Any]] | None, JSONResponse | None]:
    """Parse and validate the webhook body from the request.

    This function handles both form data and JSON requests, and performs
    basic validation on the parsed body.

    Args:
        request: The FastAPI request object

    Returns:
        Tuple containing:
        - The parsed webhook body (dict or list) or None if parsing failed
        - An error response or None if successful
    """
    try:
        content_type = request.headers.get("content-type", "")
        logger.info("Processing webhook with content type: %s", content_type)
        logger.info(f"REQUEST HEADERS: {dict(request.headers.items())}")

        if (
            "multipart/form-data" in content_type
            or "application/x-www-form-urlencoded" in content_type
        ):
            # Handle form data
            logger.info("Handling as form data")
            body, error_response = await _handle_form_data(request)
        else:
            # Handle JSON data (default)
            logger.info("Handling as JSON data")
            raw_body = await request.body()
            logger.info(f"RAW JSON BODY: {raw_body.decode('utf-8', errors='replace')}")
            body, error_response = await _handle_json_body(request)

        if error_response:
            logger.info(
                f"Error response generated: " f"{error_response.body.decode('utf-8')}"
            )
            return None, error_response

        if not body:
            logger.warning("Empty webhook body after parsing")
            # Check if this is a Mandrill request by inspecting the user agent
            user_agent = request.headers.get("user-agent", "")
            if "Mandrill" in user_agent:
                logger.info("Detected Mandrill test webhook with empty body, accepting")
                # Accept empty bodies from Mandrill for testing purposes
                return [], None

            return None, JSONResponse(
                content={
                    "status": "error",
                    "message": "Empty webhook body",
                },
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Log the body structure
        if isinstance(body, list):
            logger.info(f"Body is a list with {len(body)} items")
            if body:
                logger.info(
                    "First item keys: "
                    f"{list(body[0].keys()) if isinstance(body[0], dict) else 'Not a dict'}"
                )
        elif isinstance(body, dict):
            logger.info(f"Body is a dict with keys: {list(body.keys())}")
        else:
            logger.info(f"Body is of type: {type(body)}")

        # Handle special cases
        ping_response = _handle_ping_event(body)
        if ping_response:
            return None, ping_response

        empty_response = _handle_empty_events(body)
        if empty_response:
            return None, empty_response

        return body, None
    except Exception as e:
        logger.error("Error in _prepare_webhook_body: %s", str(e))
        import traceback

        logger.error(f"Exception traceback: {traceback.format_exc()}")
        return None, JSONResponse(
            content={
                "status": "error",
                "message": f"Failed to process webhook but acknowledged: {str(e)}",
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )
