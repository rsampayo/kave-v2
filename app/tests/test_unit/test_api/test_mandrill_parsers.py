"""Tests for the Mandrill webhook parsers module."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import Request, status

from app.api.v1.endpoints.webhooks.mandrill.parsers import (
    _create_json_error_response,
    _handle_empty_events,
    _handle_form_data,
    _handle_json_body,
    _handle_ping_event,
    _is_empty_event_list,
    _is_ping_event,
    _log_parsed_body_info,
    _parse_json_from_bytes,
    _parse_json_from_request,
    _parse_json_from_string,
)


@pytest.mark.asyncio
async def test_handle_form_data_success() -> None:
    """Test successful form data handling from Mandrill webhook."""
    # Create valid form data
    mandrill_events = (
        '[{"event":"inbound", "_id":"123", "msg":{"from_email":"test@example.com"}}]'
    )

    # Create a proper mock request with MagicMock
    mock_request = MagicMock(spec=Request)
    mock_request.form = AsyncMock(return_value={"mandrill_events": mandrill_events})

    # Call the function
    body, error = await _handle_form_data(mock_request)

    # Verify results
    assert error is None
    assert isinstance(body, list)
    assert len(body) == 1
    assert body[0]["event"] == "inbound"
    assert body[0]["_id"] == "123"
    assert body[0]["msg"]["from_email"] == "test@example.com"


@pytest.mark.asyncio
async def test_handle_form_data_missing_events() -> None:
    """Test form data handling when mandrill_events is missing."""
    # Create a mock request with MagicMock
    mock_request = MagicMock(spec=Request)
    mock_request.form = AsyncMock(return_value={"some_other_field": "value"})

    # Call the function
    body, error = await _handle_form_data(mock_request)

    # Verify results
    assert body is None
    assert error is not None
    assert error.status_code == 400
    assert "Missing 'mandrill_events'" in error.body.decode()


@pytest.mark.asyncio
async def test_handle_form_data_invalid_json() -> None:
    """Test form data handling when mandrill_events contains invalid JSON."""
    # Create a mock request with MagicMock
    mock_request = MagicMock(spec=Request)
    mock_request.form = AsyncMock(return_value={"mandrill_events": "this is not json"})

    # Call the function
    body, error = await _handle_form_data(mock_request)

    # Verify results
    assert body is None
    assert error is not None
    assert error.status_code == 400
    assert "Invalid Mandrill webhook format" in error.body.decode()


@pytest.mark.asyncio
async def test_handle_form_data_form_exception() -> None:
    """Test form data handling when an exception occurs during form processing."""
    # Create a mock request that raises an exception when form() is called
    mock_request = AsyncMock(spec=Request)
    mock_request.form.side_effect = Exception("Form processing error")

    # Call the function
    body, error = await _handle_form_data(mock_request)

    # Verify results
    assert body is None
    assert error is not None
    assert error.status_code == 400
    assert "Error processing form data" in error.body.decode()


@pytest.mark.asyncio
async def test_handle_json_body_success() -> None:
    """Test successful JSON body handling from webhook request."""
    # Create a mock request with valid JSON
    mock_request = AsyncMock(spec=Request)
    # Set the body return value first as the code tries to read the body first
    mock_request.body.return_value = b'{"event": "inbound", "data": {"key": "value"}}'
    mock_request.json.return_value = {"event": "inbound", "data": {"key": "value"}}

    # Call the function
    body, error = await _handle_json_body(mock_request)

    # Verify results
    assert error is None
    assert isinstance(body, dict)
    assert body["event"] == "inbound"
    assert body["data"]["key"] == "value"


@pytest.mark.asyncio
async def test_handle_json_body_error() -> None:
    """Test JSON body handling when an exception occurs during JSON parsing."""
    # Create a mock request that raises an exception when json() is called
    mock_request = AsyncMock(spec=Request)
    # Set a body that will fail to parse as JSON
    mock_request.body.return_value = b'{"invalid json syntax"'
    mock_request.json.side_effect = Exception("Invalid JSON")

    # Call the function
    body, error = await _handle_json_body(mock_request)

    # Verify results
    assert body is None
    assert error is not None
    assert error.status_code == 400
    assert "Failed to process webhook" in error.body.decode()


@pytest.mark.asyncio
async def test_parse_json_from_bytes_success() -> None:
    """Test successful parsing of JSON from bytes."""
    raw_bytes = b'{"key": "value"}'
    result = await _parse_json_from_bytes(raw_bytes)
    assert result == {"key": "value"}


@pytest.mark.asyncio
async def test_parse_json_from_string_success() -> None:
    """Test successful parsing of JSON from string."""
    raw_bytes = b'{"key": "value"}'
    result = await _parse_json_from_string(raw_bytes)
    assert result == {"key": "value"}


@pytest.mark.asyncio
async def test_parse_json_from_request_success() -> None:
    """Test successful parsing of JSON from request."""
    mock_request = AsyncMock(spec=Request)
    mock_request.json.return_value = {"key": "value"}
    result = await _parse_json_from_request(mock_request)
    assert result == {"key": "value"}


def test_log_parsed_body_info(caplog) -> None:
    """Test logging of parsed body info."""
    # Test with a list
    _log_parsed_body_info([1, 2, 3])
    # Test with a dict
    _log_parsed_body_info({"a": 1, "b": 2})
    # Test with another type
    _log_parsed_body_info(123)
    # We just verify no exceptions are raised


def test_create_json_error_response() -> None:
    """Test creation of JSON error response."""
    response = _create_json_error_response("Test error")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    response_data = json.loads(response.body.decode())
    assert response_data["status"] == "error"
    assert response_data["message"] == "Failed to process webhook: Test error"


def test_is_ping_event() -> None:
    """Test detection of ping events."""
    # Test with ping event in dict
    assert _is_ping_event({"type": "ping"}) is True
    assert _is_ping_event({"event": "ping"}) is True

    # Test with ping event in list
    assert _is_ping_event([{"type": "ping"}]) is True
    assert _is_ping_event([{"event": "ping"}]) is True

    # Test with non-ping event
    assert _is_ping_event({"type": "not_ping"}) is False
    assert _is_ping_event([{"type": "not_ping"}]) is False

    # Test with empty list
    assert _is_ping_event([]) is False

    # Test with invalid type - add type ignore for testing
    assert _is_ping_event(123) is False  # type: ignore


def test_is_empty_event_list() -> None:
    """Test detection of empty event lists."""
    # Test with empty list
    assert _is_empty_event_list([]) is True

    # Test with non-empty list
    assert _is_empty_event_list([{"type": "ping"}]) is False

    # Test with dict
    assert _is_empty_event_list({"type": "ping"}) is False

    # Test with invalid type - add type ignore for testing
    assert _is_empty_event_list(123) is False  # type: ignore


def test_handle_empty_events() -> None:
    """Test handling of empty events."""
    # Test with empty list
    response = _handle_empty_events([])
    assert response is not None
    assert response.status_code == status.HTTP_200_OK
    response_data = json.loads(response.body.decode())
    assert response_data["status"] == "success"

    # Test with non-empty list
    assert _handle_empty_events([{"type": "ping"}]) is None

    # Test with dict
    assert _handle_empty_events({"type": "ping"}) is None


def test_handle_ping_event() -> None:
    """Test handling of ping events."""
    # Test with ping event in dict
    response = _handle_ping_event({"type": "ping"})
    assert response is not None
    assert response.status_code == status.HTTP_200_OK
    response_data = json.loads(response.body.decode())
    assert response_data["status"] == "success"
    assert response_data["message"] == "Ping acknowledged"

    # Test with ping event in list
    response = _handle_ping_event([{"type": "ping"}])
    assert response is not None
    assert response.status_code == status.HTTP_200_OK

    # Test with non-ping event
    assert _handle_ping_event({"type": "not_ping"}) is None
    assert _handle_ping_event([{"type": "not_ping"}]) is None
