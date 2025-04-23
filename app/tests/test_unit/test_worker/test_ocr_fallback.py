"""Unit tests for OCR fallback in PDF processing task."""

from unittest.mock import AsyncMock, MagicMock, patch


def test_process_pdf_attachment_ocr_fallback():
    """Test that the task uses OCR fallback when direct text extraction returns minimal text."""
    # Import the task
    from app.worker.tasks import process_pdf_attachment

    # Setup mocks
    mock_db_session = MagicMock()
    mock_db_session.close = MagicMock()
    # Create a get method that will track calls
    mock_db_session.get = MagicMock(return_value=None)

    mock_attachment = MagicMock()
    mock_attachment.id = 1
    mock_attachment.storage_uri = "test-storage-uri"

    mock_storage = MagicMock()
    mock_storage_get_file = AsyncMock(return_value=b"pdfbytes")
    mock_storage.get_file = mock_storage_get_file

    # Create mock document and pages
    mock_doc = MagicMock()
    mock_doc.page_count = 3

    # Create mock pages with different direct text extraction results
    mock_pages = []
    # Page 1: Good direct text (no OCR needed)
    mock_page1 = MagicMock()
    mock_page1.get_text.return_value = (
        "This is sufficient text from direct extraction on page 1."
    )

    # Page 2: Minimal direct text (OCR needed)
    mock_page2 = MagicMock()
    mock_page2.get_text.return_value = "   "  # Just whitespace
    mock_pixmap2 = MagicMock()
    mock_pixmap2.tobytes.return_value = b"image_bytes_page2"
    mock_page2.get_pixmap.return_value = mock_pixmap2

    # Page 3: Empty direct text (OCR needed)
    mock_page3 = MagicMock()
    mock_page3.get_text.return_value = ""  # Empty string
    mock_pixmap3 = MagicMock()
    mock_pixmap3.tobytes.return_value = b"image_bytes_page3"
    mock_page3.get_pixmap.return_value = mock_pixmap3

    mock_pages = [mock_page1, mock_page2, mock_page3]

    # Make doc.load_page return the appropriate mock page
    mock_doc.load_page = lambda page_num: mock_pages[page_num]

    # Mock Image and pytesseract
    mock_image = MagicMock()
    mock_image_open = MagicMock(return_value=mock_image)

    # Test the OCR fallback
    with (
        patch("app.worker.tasks.get_session", return_value=mock_db_session),
        patch("app.worker.tasks.StorageService", return_value=mock_storage),
        patch("app.worker.tasks.async_to_sync") as mock_async_to_sync,
        patch("app.worker.tasks.fitz.open", return_value=mock_doc),
        patch("app.worker.tasks.settings.PDF_USE_SINGLE_TRANSACTION", True),
        patch("app.worker.tasks.Image.open", mock_image_open),
        patch("app.worker.tasks.pytesseract.image_to_string") as mock_image_to_string,
        patch("app.worker.tasks.settings.TESSERACT_LANGUAGES", ["eng"]),
        patch("app.worker.tasks.settings.TESSERACT_PATH", "/path/to/tesseract"),
    ):

        # Configure mocks
        mock_db_session.get.return_value = mock_attachment

        # Setup async_to_sync to handle different types of calls
        def fake_async_to_sync(func):
            if func == mock_db_session.close:
                return lambda: None
            elif func == mock_db_session.commit:
                return lambda: None
            elif func == mock_db_session.rollback:
                return lambda: None
            elif func == mock_db_session.get:
                # Return the mock directly
                return mock_db_session.get
            else:
                return lambda *args, **kwargs: b"pdfbytes"

        mock_async_to_sync.side_effect = fake_async_to_sync
        mock_db_session.begin = MagicMock(
            return_value=MagicMock(__enter__=MagicMock(), __exit__=MagicMock())
        )

        # OCR results for each page
        mock_image_to_string.side_effect = [
            "OCR text for page 2 from Tesseract",
            "OCR text for page 3 from Tesseract",
        ]

        # Call the task
        result = process_pdf_attachment(attachment_id=1)

        # Verify direct text was used for page 1
        assert mock_page1.get_text.call_count == 1
        assert (
            not hasattr(mock_page1, "get_pixmap")
            or mock_page1.get_pixmap.call_count == 0
        )  # No OCR for page 1

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
    with (
        patch("app.worker.tasks.get_session", return_value=mock_db_session),
        patch("app.worker.tasks.StorageService", return_value=mock_storage),
        patch("app.worker.tasks.async_to_sync") as mock_async_to_sync,
        patch("app.worker.tasks.fitz.open", return_value=mock_doc),
        patch("app.worker.tasks.settings.PDF_USE_SINGLE_TRANSACTION", True),
        patch("app.worker.tasks.Image.open", mock_image_open),
        patch(
            "app.worker.tasks.pytesseract.image_to_string",
            side_effect=Exception("OCR error"),
        ),
        patch("app.worker.tasks.settings.TESSERACT_LANGUAGES", ["eng"]),
        patch("app.worker.tasks.settings.TESSERACT_PATH", "/path/to/tesseract"),
    ):

        # Reset call counts
        for mock_page in mock_pages:
            mock_page.get_text.reset_mock()
            if hasattr(mock_page, "get_pixmap"):
                mock_page.get_pixmap.reset_mock()
        mock_image_open.reset_mock()

        # Configure mocks
        mock_db_session.get.return_value = mock_attachment

        # Setup async_to_sync
        mock_async_to_sync.side_effect = fake_async_to_sync
        mock_db_session.begin = MagicMock(
            return_value=MagicMock(__enter__=MagicMock(), __exit__=MagicMock())
        )

        # Call the task - should still succeed with original text when OCR fails
        result = process_pdf_attachment(attachment_id=1)

        # Verify OCR was attempted for pages 2 and 3
        assert mock_page2.get_pixmap.call_count == 1
        assert mock_page3.get_pixmap.call_count == 1
        assert mock_image_open.call_count == 2

        # Verify all pages were processed (using direct text when OCR fails)
        assert "pages: 3" in result.lower()
        assert "success: 3" in result.lower()
