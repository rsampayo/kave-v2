# Step 8: Implement Task: Pytesseract OCR Fallback

## Goal
Enhance the page processing loop to use `pytesseract` OCR if `page.get_text()` returns minimal text.

## TDD (RED)
Write a test in `app/tests/test_unit/test_worker.py` to verify that the task correctly falls back to OCR when direct text extraction yields minimal results.

```python
# app/tests/test_unit/test_worker.py - add or update
import pytest
from unittest.mock import patch, MagicMock, AsyncMock, call

def test_process_pdf_attachment_ocr_fallback():
    """Test that the task uses OCR fallback when direct text extraction returns minimal text."""
    # Import the task
    from app.worker.tasks import process_pdf_attachment
    
    # Setup mocks
    mock_db_session = MagicMock()
    mock_attachment = MagicMock()
    mock_attachment.id = 1
    mock_attachment.storage_uri = "test-storage-uri"
    
    mock_storage = MagicMock()
    mock_storage_get_file = AsyncMock(return_value=b'pdfbytes')
    mock_storage.get_file = mock_storage_get_file
    
    # Create mock document and pages
    mock_doc = MagicMock()
    mock_doc.page_count = 3
    
    # Create mock pages with different direct text extraction results
    mock_pages = []
    # Page 1: Good direct text (no OCR needed)
    mock_page1 = MagicMock()
    mock_page1.get_text.return_value = "This is sufficient text from direct extraction on page 1."
    
    # Page 2: Minimal direct text (OCR needed)
    mock_page2 = MagicMock()
    mock_page2.get_text.return_value = "   "  # Just whitespace
    mock_pixmap2 = MagicMock()
    mock_pixmap2.tobytes.return_value = b'image_bytes_page2'
    mock_page2.get_pixmap.return_value = mock_pixmap2
    
    # Page 3: Empty direct text (OCR needed)
    mock_page3 = MagicMock()
    mock_page3.get_text.return_value = ""  # Empty string
    mock_pixmap3 = MagicMock()
    mock_pixmap3.tobytes.return_value = b'image_bytes_page3'
    mock_page3.get_pixmap.return_value = mock_pixmap3
    
    mock_pages = [mock_page1, mock_page2, mock_page3]
    
    # Make doc.load_page return the appropriate mock page
    mock_doc.load_page = lambda page_num: mock_pages[page_num]
    
    # Mock Image and pytesseract
    mock_image = MagicMock()
    mock_image_open = MagicMock(return_value=mock_image)
    
    # Test the OCR fallback
    with patch('app.worker.tasks.get_session', return_value=mock_db_session), \
         patch('app.worker.tasks.StorageService', return_value=mock_storage), \
         patch('app.worker.tasks.async_to_sync') as mock_async_to_sync, \
         patch('app.worker.tasks.fitz.open', return_value=mock_doc), \
         patch('app.worker.tasks.settings.PDF_USE_SINGLE_TRANSACTION', True), \
         patch('app.worker.tasks.Image.open', mock_image_open), \
         patch('app.worker.tasks.pytesseract.image_to_string') as mock_image_to_string, \
         patch('app.worker.tasks.settings.TESSERACT_LANGUAGES', ["eng"]), \
         patch('app.worker.tasks.settings.TESSERACT_PATH', "/path/to/tesseract"):
        
        # Configure mocks
        mock_db_session.get.return_value = mock_attachment
        mock_async_to_sync.return_value = lambda func: b'pdfbytes'
        mock_db_session.begin = MagicMock(return_value=MagicMock(__enter__=MagicMock(), __exit__=MagicMock()))
        
        # OCR results for each page
        mock_image_to_string.side_effect = [
            "OCR text for page 2 from Tesseract",
            "OCR text for page 3 from Tesseract"
        ]
        
        # Call the task
        result = process_pdf_attachment(MagicMock(), 1)
        
        # Verify direct text was used for page 1
        assert mock_page1.get_text.call_count == 1
        assert mock_page1.get_pixmap.call_count == 0  # No OCR for page 1
        
        # Verify OCR was used for pages 2 and 3
        assert mock_page2.get_text.call_count == 1
        assert mock_page2.get_pixmap.call_count == 1  # OCR for page 2
        assert mock_page3.get_text.call_count == 1
        assert mock_page3.get_pixmap.call_count == 1  # OCR for page 3
        
        # Verify Image.open was called twice (for pages 2 and 3)
        assert mock_image_open.call_count == 2
        
        # Verify pytesseract.image_to_string was called twice (for pages 2 and 3)
        assert mock_image_to_string.call_count == 2
        
        # Verify first call to pytesseract.image_to_string used correct language
        mock_image_to_string.assert_any_call(mock_image, lang="eng")
        
        # Verify successful processing
        assert "pages: 3" in result.lower()
        assert "success: 3" in result.lower()
    
    # Test OCR error handling
    with patch('app.worker.tasks.get_session', return_value=mock_db_session), \
         patch('app.worker.tasks.StorageService', return_value=mock_storage), \
         patch('app.worker.tasks.async_to_sync') as mock_async_to_sync, \
         patch('app.worker.tasks.fitz.open', return_value=mock_doc), \
         patch('app.worker.tasks.settings.PDF_USE_SINGLE_TRANSACTION', True), \
         patch('app.worker.tasks.Image.open', mock_image_open), \
         patch('app.worker.tasks.pytesseract.image_to_string', side_effect=Exception("OCR error")), \
         patch('app.worker.tasks.settings.TESSERACT_LANGUAGES', ["eng"]), \
         patch('app.worker.tasks.settings.TESSERACT_PATH', "/path/to/tesseract"):
        
        # Reset call counts
        for mock_page in mock_pages:
            mock_page.get_text.reset_mock()
            if hasattr(mock_page, 'get_pixmap'):
                mock_page.get_pixmap.reset_mock()
        mock_image_open.reset_mock()
        
        # Configure mocks
        mock_db_session.get.return_value = mock_attachment
        mock_async_to_sync.return_value = lambda func: b'pdfbytes'
        mock_db_session.begin = MagicMock(return_value=MagicMock(__enter__=MagicMock(), __exit__=MagicMock()))
        
        # Call the task - should still succeed with original text when OCR fails
        result = process_pdf_attachment(MagicMock(), 1)
        
        # Verify OCR was attempted for pages 2 and 3
        assert mock_page2.get_pixmap.call_count == 1
        assert mock_page3.get_pixmap.call_count == 1
        assert mock_image_open.call_count == 2
        
        # Verify all pages were processed (using direct text when OCR fails)
        assert "pages: 3" in result.lower()
        assert "success: 3" in result.lower()
```

## Implementation (GREEN)

### 1. Add Required Imports

Add the necessary imports to `app/worker/tasks.py`:

```python
# Add these imports to app/worker/tasks.py
import pytesseract
from PIL import Image
import io
```

### 2. Update PyMuPDF Text Extraction Process with OCR Fallback

Modify the page processing loop in the `process_pdf_attachment` task to add OCR fallback when direct text extraction yields minimal results:

```python
# Replace the direct text extraction logic in both transaction modes with this OCR fallback code
# Single transaction mode:
for page_num in range(total_pages):
    try:
        page = doc.load_page(page_num)
        # Direct text extraction first
        direct_text = page.get_text("text") or ""  # Direct text extraction, ensure string

        page_text_to_save = direct_text  # Default to direct extraction

        # OCR Fallback Logic
        TEXT_LENGTH_THRESHOLD = 50  # Chars; Tune this threshold
        if len(direct_text.strip()) < TEXT_LENGTH_THRESHOLD:
            logger.info(f"Task {task_id}: Page {page_num+1} has little direct text ({len(direct_text.strip())} chars), attempting OCR.")
            try:
                # Configure Tesseract path from settings
                pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_PATH

                # Render page to an image (e.g., PNG) at higher DPI for better OCR
                zoom = 4  # zoom factor 4 => 300 DPI (approx)
                mat = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=mat, alpha=False)  # alpha=False for non-transparent image

                img_data = pix.tobytes("png")  # Use PNG format

                if not img_data:
                    logger.warning(f"Task {task_id}: Failed to get image bytes for page {page_num+1}.")
                else:
                    img = Image.open(io.BytesIO(img_data))

                    # Perform OCR using configured languages
                    ocr_text = pytesseract.image_to_string(
                        img,
                        lang="+".join(settings.TESSERACT_LANGUAGES)
                    )

                    if ocr_text.strip():  # Only use OCR text if it's not empty
                        page_text_to_save = ocr_text
                        logger.info(
                            f"Task {task_id}: OCR successful for page {page_num+1}, "
                            f"length: {len(ocr_text)}, "
                            f"languages: {'+'.join(settings.TESSERACT_LANGUAGES)}"
                        )
                    else:
                        logger.warning(
                            f"Task {task_id}: OCR produced no text for page {page_num+1}, "
                            f"keeping direct text (length: {len(direct_text)})"
                        )

            except ImportError:
                logger.error(
                    f"Task {task_id}: Pytesseract or Pillow not installed. "
                    f"Cannot perform OCR fallback. Path: {settings.TESSERACT_PATH}"
                )
                # Sticks with direct_text
            except pytesseract.TesseractNotFoundError:
                logger.error(
                    f"Task {task_id}: Tesseract executable not found at {settings.TESSERACT_PATH}. "
                    "Ensure it's installed and path is correct."
                )
                # Sticks with direct_text
            except Exception as ocr_err:
                # Catch other potential errors (PIL issues, tesseract runtime errors)
                logger.warning(
                    f"Task {task_id}: OCR failed for page {page_num+1} of attachment {attachment_id}: {ocr_err}",
                    exc_info=True
                )
                # Sticks with direct_text (which is already in page_text_to_save)

        # Create and Save AttachmentTextContent record with the best text we have
        text_content_entry = AttachmentTextContent(
            attachment_id=attachment_id,
            page_number=page_num + 1,  # Page numbers are 1-based
            text_content=page_text_to_save.strip() if page_text_to_save else None
        )
        db.add(text_content_entry)
        processed_pages += 1
        logger.debug(f"Task {task_id}: Added page {page_num + 1}/{total_pages} content for attachment {attachment_id}")

    except Exception as page_err:
        errors_on_pages += 1
        logger.error(f"Task {task_id}: Error processing page {page_num + 1} for attachment {attachment_id}: {page_err}")
        check_error_threshold()  # May raise ValueError if too many errors
        # Continue to next page if within error threshold
```

Make the same changes in the non-single transaction mode's page processing loop as well.

## Quality Check (REFACTOR)
Run the following code quality tools and fix any issues:
```bash
black .
isort .
flake8 .
mypy app
```

## Testing (REFACTOR)
Run the test to verify the OCR fallback logic:
```bash
pytest app/tests/test_unit/test_worker.py::test_process_pdf_attachment_ocr_fallback
```

The test should now pass.

## Self-Verification Checklist
- [ ] Are the required imports added (`pytesseract`, `PIL.Image`, `io`)?
- [ ] Is the text length threshold check implemented?
- [ ] Is Tesseract configured from settings?
- [ ] Is the page rendering to image implemented (with `get_pixmap`)?
- [ ] Is the image conversion and OCR process implemented correctly?
- [ ] Are OCR results used only if they're not empty?
- [ ] Is proper error handling in place for OCR failures?
- [ ] Is the original direct text kept if OCR fails?
- [ ] Is the OCR fallback applied in both transaction modes?
- [ ] Do all tests pass?
- [ ] Do all quality checks pass?

After completing this step, stop and request approval before proceeding to Step 9. 