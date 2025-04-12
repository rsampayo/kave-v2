"""Webhook attachments processing module.

Contains functions for normalizing and processing email attachments.
"""

import json
import logging
from typing import Any

from app.api.endpoints.webhooks.common.mime_utils import _decode_mime_header

# Set up logging
logger = logging.getLogger(__name__)


def _normalize_attachments(
    attachments: list[dict[str, Any]] | dict[str, Any] | str | None,
) -> list[dict[str, Any]]:
    """Normalize attachment data to a consistent format.

    Handles multiple input formats:
    - List of attachment dictionaries
    - Single attachment as a dictionary
    - JSON string with attachment data
    - Dictionary with nested attachment objects

    Each normalized attachment will have at least:
    - name: The filename (MIME-decoded if needed)
    - type: The MIME type
    - content: The attachment content (if present)

    Args:
        attachments: Attachment data in various formats

    Returns:
        List[Dict[str, Any]]: List of normalized attachment dictionaries
    """
    if not attachments:
        return []

    # Handle JSON string format
    if isinstance(attachments, str):
        return _parse_attachments_from_string(attachments)

    # Handle list format (most common case)
    if isinstance(attachments, list):
        return _process_attachment_list(attachments)

    # Handle dictionary format - could be a single attachment or a dict of attachments
    if isinstance(attachments, dict):
        return _parse_attachments_from_dict(attachments)

    # Any other format, log warning and return empty list
    logger.warning("Unsupported attachment format: %s", type(attachments))
    return []


def _process_attachment_list(attachments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Process a list of attachment dictionaries.

    Args:
        attachments: List of attachment dictionaries

    Returns:
        List[Dict[str, Any]]: List of normalized attachment dictionaries
    """
    normalized = []
    for attachment in attachments:
        if isinstance(attachment, dict):
            # Copy the attachment to avoid modifying the original
            normalized_attachment = attachment.copy()

            # Decode the filename if present
            if "name" in normalized_attachment:
                normalized_attachment["name"] = _decode_mime_header(
                    normalized_attachment["name"]
                )

            normalized.append(normalized_attachment)

    return normalized


def _parse_attachment_string(attachment_string: str) -> list[dict[str, Any]]:
    """Parse a JSON attachment string.

    Args:
        attachment_string: JSON string containing attachment data

    Returns:
        List[Dict[str, Any]]: List of parsed attachments
    """
    try:
        parsed = json.loads(attachment_string)
        if isinstance(parsed, list):
            return _process_attachment_list(parsed)
        if isinstance(parsed, dict):
            return _parse_attachments_from_dict(parsed)
        logger.warning("Parsed JSON is neither list nor dict: %s", type(parsed))
        return []
    except json.JSONDecodeError as e:
        logger.warning("Failed to parse attachment JSON: %s", str(e))
        return []


def _parse_attachments_from_string(attachment_string: str) -> list[dict[str, Any]]:
    """Parse attachments from a JSON string.

    Args:
        attachment_string: JSON string containing attachment data

    Returns:
        List[Dict[str, Any]]: List of normalized attachment dictionaries
    """
    try:
        return _parse_attachment_string(attachment_string)
    except Exception as e:
        logger.warning("Error parsing attachment string: %s", str(e))
        return []


def _parse_attachments_from_dict(
    attachment_dict: dict[str, Any],
) -> list[dict[str, Any]]:
    """Parse attachments from a dictionary structure.

    This handles two cases:
    1. The dictionary is a single attachment with keys like 'name' and 'type'
    2. The dictionary contains multiple attachments as nested dictionaries

    Args:
        attachment_dict: Dictionary containing attachment data

    Returns:
        List[Dict[str, Any]]: List of normalized attachment dictionaries
    """
    # Check if this is a single attachment
    if "name" in attachment_dict and "type" in attachment_dict:
        # This looks like a single attachment
        result = [attachment_dict.copy()]
        # Decode the filename
        if "name" in result[0]:
            result[0]["name"] = _decode_mime_header(result[0]["name"])
        return result

    # Otherwise, it might be a dictionary of attachments
    attachments = []
    for _key, value in attachment_dict.items():
        if isinstance(value, dict) and "name" in value and "type" in value:
            # This is an attachment-like object
            attachment = value.copy()
            # Decode the filename
            if "name" in attachment:
                attachment["name"] = _decode_mime_header(attachment["name"])
            attachments.append(attachment)

    return attachments


def _decode_filenames_in_attachments(
    attachments: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Decode MIME-encoded filenames in a list of attachments.

    Args:
        attachments: List of attachment dictionaries

    Returns:
        List[Dict[str, Any]]: Attachments with decoded filenames
    """
    for attachment in attachments:
        if "name" in attachment:
            attachment["name"] = _decode_mime_header(attachment["name"])
    return attachments
