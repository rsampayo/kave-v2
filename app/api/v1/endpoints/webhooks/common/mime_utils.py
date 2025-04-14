"""MIME utility functions for webhook processing.

This module provides utilities for handling MIME-encoded text commonly found in email headers.
Its primary purpose is to decode and normalize these values for better readability within
the application. MIME encoding is often used for non-ASCII characters in email headers.

Features:
1. Decode MIME-encoded header values with proper charset handling
2. Fallback strategies for handling decoding errors
3. Support for multiple MIME encoding formats

All functions are prefixed with underscore as they are intended for internal use within
the webhook processing system.
"""

import email.header
import logging

# Set up logging
logger = logging.getLogger(__name__)


def _decode_mime_header(value: str | None) -> str | None:  # noqa: C901
    """Decode a MIME-encoded header value.

    Args:
        value: The MIME-encoded header value

    Returns:
        The decoded header value, or the original value if decoding fails
    """
    if value is None:
        return None

    if not value:
        return value

    try:
        # Check if this looks like a MIME-encoded header
        if "=?" in value and "?=" in value:
            # Parse the header value
            decoded_parts = []
            for decoded, charset in email.header.decode_header(value):
                if isinstance(decoded, bytes):
                    try:
                        # Try to decode using the specified charset
                        if charset:
                            decoded_part = decoded.decode(charset)
                        else:
                            # If no charset specified, try utf-8, then latin-1
                            try:
                                decoded_part = decoded.decode("utf-8")
                            except UnicodeDecodeError:
                                decoded_part = decoded.decode("latin-1")
                    except (UnicodeDecodeError, LookupError):
                        # Fallback to a safe decoding if specified charset fails
                        decoded_part = decoded.decode("latin-1", errors="replace")
                else:
                    # Already a string
                    decoded_part = decoded
                decoded_parts.append(decoded_part)

            # Join all parts
            return "".join(decoded_parts)
        return value
    except Exception as e:
        # If any error occurs during decoding, return the original value
        logger.warning("Error decoding MIME header: %s", e)
        return value
