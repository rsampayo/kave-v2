#!/usr/bin/env python
"""
Test the application's OCR functionality.
This script creates a test PDF with some text and tests the OCR extraction
with the app's settings.
"""

import io
import os
import sys
import tempfile

import fitz  # PyMuPDF
import pytesseract
from PIL import Image, ImageDraw, ImageFont

from app.core.config import settings


def create_text_image(
    text="Test OCR", size=(600, 200), bg_color="white", text_color="black"
):
    """Create a simple image with text."""
    # Create a new image with white background
    image = Image.new("RGB", size, bg_color)

    # Get a drawing context
    draw = ImageDraw.Draw(image)

    # Try to use a default font
    try:
        font = ImageFont.truetype("Arial", 40)
    except IOError:
        # If Arial is not available, use default font
        font = ImageFont.load_default()

    # Calculate text position to center it
    if hasattr(draw, "textsize"):
        text_width, text_height = draw.textsize(text, font=font)
    elif hasattr(font, "getbbox"):
        bbox = font.getbbox(text)
        text_width, text_height = bbox[2] - bbox[0], bbox[3] - bbox[1]
    else:
        # Fallback to a reasonable default
        text_width, text_height = len(text) * 20, 40

    position = ((size[0] - text_width) // 2, (size[1] - text_height) // 2)

    # Draw the text
    draw.text(position, text, fill=text_color, font=font)

    return image


def create_test_pdf(filename, text="Test OCR PDF Document"):
    """Create a PDF with text for testing."""
    # Create a new PDF
    doc = fitz.open()

    # Add a page with direct text
    page1 = doc.new_page()
    page1.insert_text((50, 50), f"Direct Text Page: {text}")

    # Add a page with an image (will require OCR)
    page2 = doc.new_page()
    img = create_text_image(f"Image Page: {text}")

    # Convert PIL Image to bytes
    img_bytes = io.BytesIO()
    img.save(img_bytes, format="PNG")
    img_bytes.seek(0)

    # Insert the image into the PDF
    img_xref = page2.insert_image(rect=(50, 50, 550, 250), stream=img_bytes.getvalue())

    # Save the PDF
    doc.save(filename)
    doc.close()

    return filename


def test_app_ocr():
    """Test the OCR functionality using app settings."""
    # Print current settings
    print(f"TESSERACT_PATH setting: {settings.TESSERACT_PATH}")
    print(f"Effective Tesseract path: {settings.effective_tesseract_path}")
    print(f"Current TESSERACT_LANGUAGES: {settings.TESSERACT_LANGUAGES}")

    # Set tesseract path from settings
    pytesseract.pytesseract.tesseract_cmd = settings.effective_tesseract_path

    # Create a temporary PDF for testing
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        pdf_path = tmp.name

    try:
        # Create test PDF
        test_text = "OCR Test for Application"
        create_test_pdf(pdf_path, test_text)
        print(f"Created test PDF at: {pdf_path}")

        # Open the PDF and test the OCR
        doc = fitz.open(pdf_path)

        # Page 1 should have direct text
        page1 = doc[0]
        direct_text = page1.get_text()
        print(f"Page 1 direct text: {direct_text}")

        # Page 2 has image-based text, extract via OCR
        page2 = doc[1]
        # Convert page to an image
        pix = page2.get_pixmap(matrix=fitz.Matrix(4, 4), alpha=False)
        img_data = pix.tobytes("png")
        img = Image.open(io.BytesIO(img_data))

        # Perform OCR
        langs = "+".join(settings.TESSERACT_LANGUAGES)
        ocr_text = pytesseract.image_to_string(img, lang=langs)
        print(f"Page 2 OCR text: {ocr_text}")

        # Check results
        if test_text in direct_text:
            print("✅ Direct text extraction PASSED!")
        else:
            print("❌ Direct text extraction FAILED!")

        if "Image Page" in ocr_text and test_text in ocr_text:
            print("✅ OCR text extraction PASSED!")
        else:
            print("❌ OCR text extraction FAILED!")

    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        return False
    finally:
        # Clean up
        if os.path.exists(pdf_path):
            os.unlink(pdf_path)

    return True


if __name__ == "__main__":
    test_app_ocr()
