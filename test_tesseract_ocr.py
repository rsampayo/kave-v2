#!/usr/bin/env python
"""
Test script to verify Tesseract OCR functionality.
This script creates a simple image with text, then uses pytesseract to extract the text.
"""

import io

import pytesseract
from PIL import Image, ImageDraw, ImageFont


def create_text_image(
    text="Hello OCR", size=(300, 100), bg_color="white", text_color="black"
):
    """Create a simple image with text."""
    # Create a new image with white background
    image = Image.new("RGB", size, bg_color)

    # Get a drawing context
    draw = ImageDraw.Draw(image)

    # Try to use a default font
    try:
        font = ImageFont.truetype("Arial", 30)
    except IOError:
        # If Arial is not available, use default font
        font = ImageFont.load_default()

    # Calculate text position to center it
    # Handle different versions of PIL/Pillow for text size calculation
    if hasattr(draw, "textsize"):
        text_width, text_height = draw.textsize(text, font=font)
    elif hasattr(font, "getbbox"):
        bbox = font.getbbox(text)
        text_width, text_height = bbox[2] - bbox[0], bbox[3] - bbox[1]
    else:
        # Fallback to a reasonable default
        text_width, text_height = len(text) * 15, 30

    position = ((size[0] - text_width) // 2, (size[1] - text_height) // 2)

    # Draw the text
    draw.text(position, text, fill=text_color, font=font)

    return image


def test_ocr():
    """Test OCR functionality with pytesseract."""
    print("Testing OCR functionality...")

    # Create an image with text
    test_text = "Hello OCR World"
    image = create_text_image(test_text)

    # Print OCR configuration
    print(f"Tesseract version: {pytesseract.get_tesseract_version()}")
    print(f"Tesseract path: {pytesseract.pytesseract.tesseract_cmd}")

    # Extract text using pytesseract
    try:
        extracted_text = pytesseract.image_to_string(image).strip()
        print(f"Original text: '{test_text}'")
        print(f"Extracted text: '{extracted_text}'")

        if test_text in extracted_text:
            print("✅ OCR Test PASSED!")
        else:
            print("❌ OCR Test FAILED - Text didn't match")

    except Exception as e:
        print(f"❌ OCR Test FAILED with error: {e}")
        return False

    return True


if __name__ == "__main__":
    # Try to run with default tesseract path
    success = test_ocr()

    if not success:
        # If failed, try setting the path explicitly
        print("\nRetrying with explicit tesseract path...")
        pytesseract.pytesseract.tesseract_cmd = "/usr/local/bin/tesseract"
        success = test_ocr()
