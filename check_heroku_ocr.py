#!/usr/bin/env python
"""
Script to verify Tesseract OCR configuration on Heroku.
Deploy to Heroku and run with: heroku run python check_heroku_ocr.py
"""

import os
import subprocess
import sys
from pathlib import Path

# Try to import from app
try:
    from app.core.config import settings
    import pytesseract
    from PIL import Image
except ImportError as e:
    print(f"Failed to import required modules: {e}")
    sys.exit(1)


def run_command(cmd):
    """Run a shell command and return the output."""
    try:
        result = subprocess.run(
            cmd, shell=True, check=True, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            text=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        return f"Error: {e.stderr.strip()}"


def check_tesseract_installation():
    """Check if Tesseract is installed and configured properly."""
    
    print("\n=== Tesseract OCR Configuration Check ===\n")
    
    # 1. Check environment
    is_heroku = "DYNO" in os.environ
    runtime = "Heroku" if is_heroku else "Local"
    print(f"Runtime environment: {runtime}")
    
    # 2. Check configured paths
    print(f"TESSERACT_PATH setting: {settings.TESSERACT_PATH}")
    print(f"Effective tesseract path: {settings.effective_tesseract_path}")
    print(f"TESSERACT_LANGUAGES: {settings.TESSERACT_LANGUAGES}")
    
    # 3. Check if tesseract executable exists at the effective path
    tesseract_path = settings.effective_tesseract_path
    if Path(tesseract_path).exists():
        print(f"✅ Tesseract executable found at: {tesseract_path}")
    else:
        print(f"❌ Tesseract executable NOT found at: {tesseract_path}")
        
        # Try locating tesseract
        which_result = run_command("which tesseract")
        if not which_result.startswith("Error"):
            print(f"ℹ️ Tesseract found in PATH at: {which_result}")
    
    # 4. Check tesseract version
    try:
        version = pytesseract.get_tesseract_version()
        print(f"✅ Tesseract version: {version}")
    except Exception as e:
        print(f"❌ Failed to get Tesseract version: {e}")
    
    # 5. Check tesseract languages
    try:
        languages = run_command(f"{tesseract_path} --list-langs")
        print(f"✅ Available languages: {languages}")
    except Exception as e:
        print(f"❌ Failed to list Tesseract languages: {e}")
    
    # 6. Check if pytesseract can be used
    print("\n=== Testing OCR functionality ===\n")
    
    # Create a simple test image
    try:
        # Create a white image with black text
        img = Image.new('RGB', (200, 50), color='white')
        
        # Try running OCR on blank image
        pytesseract.pytesseract.tesseract_cmd = settings.effective_tesseract_path
        text = pytesseract.image_to_string(img)
        print(f"✅ Pytesseract successfully processed a test image")
        print(f"   Extracted text (may be empty for blank image): '{text}'")
    except Exception as e:
        print(f"❌ Failed to process image with pytesseract: {e}")
    
    # 7. Check system dependencies
    print("\n=== System Dependencies ===\n")
    
    if is_heroku:
        # On Heroku, check for Apt buildpack dependencies
        ldd_result = run_command("ldd $(which tesseract) | grep -i 'not found'")
        if ldd_result and not ldd_result.startswith("Error"):
            print(f"❌ Missing libraries for Tesseract: {ldd_result}")
        else:
            print("✅ All required libraries for Tesseract are installed")
    else:
        # On local system, check homebrew dependencies
        if sys.platform == 'darwin':  # macOS
            brew_info = run_command("brew info tesseract")
            if not brew_info.startswith("Error"):
                print("✅ Tesseract is installed via Homebrew")
            else:
                print("❌ Tesseract may not be installed via Homebrew")


if __name__ == "__main__":
    check_tesseract_installation() 