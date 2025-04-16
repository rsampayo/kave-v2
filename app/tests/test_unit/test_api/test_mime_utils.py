"""Unit tests for MIME utilities."""

from app.api.v1.endpoints.webhooks.common.mime_utils import _decode_mime_header


def test_decode_mime_header_none_value():
    """Test decoding None value."""
    result = _decode_mime_header(None)
    assert result is None


def test_decode_mime_header_empty_string():
    """Test decoding empty string."""
    result = _decode_mime_header("")
    assert result == ""


def test_decode_mime_header_non_mime_text():
    """Test decoding plain text without MIME encoding."""
    plain_text = "This is plain text"
    result = _decode_mime_header(plain_text)
    assert result == plain_text


def test_decode_mime_header_utf8():
    """Test decoding UTF-8 MIME-encoded text."""
    # "Héllo Wórld" encoded in UTF-8 MIME format
    encoded = "=?utf-8?q?H=C3=A9llo_W=C3=B3rld?="
    result = _decode_mime_header(encoded)
    assert result == "Héllo Wórld"


def test_decode_mime_header_iso_8859_1():
    """Test decoding ISO-8859-1 MIME-encoded text."""
    # "Café" encoded in ISO-8859-1 MIME format
    encoded = "=?iso-8859-1?q?Caf=E9?="
    result = _decode_mime_header(encoded)
    assert result == "Café"


def test_decode_mime_header_base64():
    """Test decoding Base64 MIME-encoded text."""
    # "Привет" (Russian for "Hello") encoded in Base64 MIME format
    encoded = "=?utf-8?b?0J/RgNC40LLQtdGC?="
    result = _decode_mime_header(encoded)
    assert result == "Привет"


def test_decode_mime_header_multiple_parts():
    """Test decoding text with multiple MIME-encoded parts."""
    # Mixed encoding: "Hello, 世界" (world in Chinese)
    encoded = "Hello, =?utf-8?b?5LiW55WM?="
    result = _decode_mime_header(encoded)
    assert result == "Hello, 世界"


def test_decode_mime_header_no_charset():
    """Test decoding when no charset is specified."""
    # MIME-encoded text without explicit charset
    encoded = "=??q?Test?="
    result = _decode_mime_header(encoded)
    # Should still attempt to decode
    assert result is not None
    assert isinstance(result, str)


def test_decode_mime_header_invalid_charset():
    """Test decoding with invalid charset specification."""
    # Specify a non-existent charset
    encoded = "=?invalid-charset?q?Test?="
    result = _decode_mime_header(encoded)
    # Should fallback to a default charset
    assert result == "Test"


def test_decode_mime_header_with_exception():
    """Test handling of exceptions during decoding."""
    # This isn't a properly formatted MIME string but contains MIME markers
    malformed = "=?utf-8?q?Incomplete MIME encoding?="

    # Should still return something without raising an exception
    result = _decode_mime_header(malformed)
    assert result is not None
    assert isinstance(result, str)
