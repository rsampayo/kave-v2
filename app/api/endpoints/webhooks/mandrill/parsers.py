"""Mandrill webhook parsers module.

Contains functions for parsing and validating webhook events from Mandrill.
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
        logger.debug("Received Mandrill form data with %s keys", len(form_data))

        if "mandrill_events" in form_data:
            # This is the standard Mandrill format
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
        logger.error("Failed to parse %s: %s", field_name, str(err))
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
            "message": error_message,
        },
        status_code=status.HTTP_400_BAD_REQUEST,
    )


async def _parse_json_body(
    request: Request,
) -> tuple[dict[str, Any] | list[dict[str, Any]] | None, JSONResponse | None]:
    """Parse and validate JSON body from various request formats.

    Args:
        request: The FastAPI request object

    Returns:
        Tuple containing:
        - The parsed JSON body (dict or list) or None if parsing failed
        - An error response or None if successful
    """
    try:
        # First try using the standard FastAPI JSON parsing
        body = await _parse_json_from_request(request)
        _log_parsed_body_info(body)
        return body, None
    except Exception as e:
        logger.debug(
            "Standard JSON parsing failed: %s, trying raw body methods", str(e)
        )
        try:
            # If that fails, try to get the raw body and parse it manually
            raw_body = await request.body()
            if not raw_body:
                logger.warning("Empty request body")
                return None, JSONResponse(
                    content={
                        "status": "error",
                        "message": "Empty request body",
                    },
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            # Try parsing raw bytes directly
            try:
                body = await _parse_json_from_bytes(raw_body)
                _log_parsed_body_info(body)
                return body, None
            except Exception as bytes_err:
                logger.debug("Failed to parse raw bytes: %s", str(bytes_err))

                # Try parsing as string
                try:
                    body = await _parse_json_from_string(raw_body)
                    _log_parsed_body_info(body)
                    return body, None
                except Exception as string_err:
                    logger.error("All JSON parsing methods failed: %s", str(string_err))
                    return None, JSONResponse(
                        content={
                            "status": "error",
                            "message": (
                                f"Failed to process webhook but acknowledged: "
                                f"{str(string_err)}"
                            ),
                        },
                        status_code=status.HTTP_400_BAD_REQUEST,
                    )
        except Exception as raw_err:
            logger.error("Error accessing raw request body: %s", str(raw_err))
            return None, JSONResponse(
                content={
                    "status": "error",
                    "message": f"Failed to process webhook but acknowledged: {str(raw_err)}",
                },
                status_code=status.HTTP_400_BAD_REQUEST,
            )


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

        if (
            "multipart/form-data" in content_type
            or "application/x-www-form-urlencoded" in content_type
        ):
            # Handle form data
            body, error_response = await _handle_form_data(request)
        else:
            # Handle JSON data (default)
            body, error_response = await _handle_json_body(request)

        if error_response:
            return None, error_response

        if not body:
            logger.warning("Empty webhook body after parsing")
            return None, JSONResponse(
                content={
                    "status": "error",
                    "message": "Empty webhook body",
                },
                status_code=status.HTTP_400_BAD_REQUEST,
            )

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
        return None, JSONResponse(
            content={
                "status": "error",
                "message": f"Failed to process webhook but acknowledged: {str(e)}",
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )
