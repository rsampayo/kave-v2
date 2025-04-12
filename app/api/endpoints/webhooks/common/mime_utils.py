"""MIME utility functions for webhook processing."""

import email.header
import logging
from typing import Optional

# Set up logging
logger = logging.getLogger(__name__)


def _decode_mime_header(value: Optional[str]) -> Optional[str]:  # noqa: C901
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
        logger.warning(f"Error decoding MIME header: {e}")
        return value
