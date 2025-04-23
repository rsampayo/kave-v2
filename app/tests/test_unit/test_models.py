"""Test the AttachmentTextContent model."""

import pytest


def test_attachment_text_content_model():
    """Test that AttachmentTextContent model exists and has the expected attributes."""
    try:
        # Import the model - this will fail until it's implemented
        from app.models.attachment_text_content import AttachmentTextContent
        from app.models.email_data import Attachment

        # Create an instance with test data
        text_content = AttachmentTextContent(
            attachment_id=1, page_number=1, text_content="Test OCR content"
        )

        # Verify attributes
        assert hasattr(text_content, "id")
        assert hasattr(text_content, "attachment_id")
        assert hasattr(text_content, "page_number")
        assert hasattr(text_content, "text_content")
        assert hasattr(text_content, "attachment")

        # Verify values
        assert text_content.attachment_id == 1
        assert text_content.page_number == 1
        assert text_content.text_content == "Test OCR content"

        # Check relationship with Attachment
        attachment = Attachment(id=1)
        assert hasattr(attachment, "text_contents")

    except ImportError:
        pytest.fail("Could not import AttachmentTextContent model")
    except Exception as e:
        pytest.fail(f"Failed to create AttachmentTextContent instance: {e}")
