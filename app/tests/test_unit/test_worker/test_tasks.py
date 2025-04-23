"""Unit tests for Celery tasks in the worker module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from celery.exceptions import Retry  # type: ignore[import-untyped]
from sqlalchemy.orm import Session


def test_process_pdf_attachment_task_definition():
    """Test that the process_pdf_attachment task is properly defined."""
    try:
        # Import the task
        from app.worker.tasks import process_pdf_attachment

        # Verify it's decorated as a Celery task
        assert hasattr(
            process_pdf_attachment, "delay"
        ), "Task should have a 'delay' method from Celery"
        assert hasattr(
            process_pdf_attachment, "apply_async"
        ), "Task should have an 'apply_async' method from Celery"

        # Simulate calling the task to verify it accepts attachment_id parameter
        # Mock the actual task execution to avoid side effects
        with patch("app.worker.tasks.process_pdf_attachment.run") as mock_run:
            process_pdf_attachment(attachment_id=1)
            mock_run.assert_called_once()

    except ImportError:
        pytest.fail("Could not import process_pdf_attachment from app.worker.tasks")
    except Exception as e:
        pytest.fail(f"Failed to verify task definition: {e}")


def test_process_pdf_attachment_data_fetching():
    """Test the data fetching part of the PDF processing task."""
    # Import the task
    from app.worker.tasks import process_pdf_attachment

    # 1. Setup mocks
    mock_db_session = MagicMock(spec=Session)
    # Add a close method that can be called via async_to_sync
    mock_db_session.close = MagicMock()

    mock_attachment = MagicMock()
    mock_attachment.id = 1
    mock_attachment.storage_uri = "test-storage-uri"

    mock_storage = MagicMock()
    mock_storage_get_file = AsyncMock(return_value=b"pdfbytes")
    mock_storage.get_file = mock_storage_get_file

    # Create a mock document with page count
    mock_doc = MagicMock()
    mock_doc.page_count = 3

    # 2. Test successful data fetching
    with (
        patch("app.worker.tasks.get_session", return_value=mock_db_session),
        patch("app.worker.tasks.StorageService", return_value=mock_storage),
        patch("app.worker.tasks.async_to_sync") as mock_async_to_sync,
        patch("app.worker.tasks.Attachment") as MockAttachment,
        patch("app.worker.tasks.fitz.open", return_value=mock_doc),
    ):

        # Configure mocks
        mock_db_session.get.return_value = mock_attachment
        MockAttachment.__name__ = "Attachment"  # For logging

        # Setup async_to_sync to handle different types of calls
        def fake_async_to_sync(func):
            if func == mock_db_session.close:
                # For session.close(), just return a callable that does nothing
                return lambda: None
            else:
                # For other cases like storage.get_file
                return lambda *args, **kwargs: b"pdfbytes"

        mock_async_to_sync.side_effect = fake_async_to_sync

        # Call the task function directly
        result = process_pdf_attachment(attachment_id=1)

        # Verify the attachment was fetched
        mock_db_session.get.assert_called_once()

        # Verify the task returned a success message
        assert "processed" in result
        assert "Pages: 3" in result

    # 3. Test attachment not found
    with (
        patch("app.worker.tasks.get_session", return_value=mock_db_session),
        patch("app.worker.tasks.StorageService", return_value=mock_storage),
        patch("app.worker.tasks.async_to_sync") as mock_async_to_sync,
        patch("app.worker.tasks.Attachment") as MockAttachment,
        patch("app.worker.tasks.fitz.open", return_value=mock_doc),
    ):

        # Configure mocks
        mock_db_session.get.return_value = None

        # Setup async_to_sync for db.close()
        mock_async_to_sync.side_effect = lambda func: (lambda: None)

        # Call the task function directly
        result = process_pdf_attachment(attachment_id=1)

        # Verify the task returned an error message
        assert "not found" in result.lower()

    # 4. Test attachment has no storage_uri
    with (
        patch("app.worker.tasks.get_session", return_value=mock_db_session),
        patch("app.worker.tasks.StorageService", return_value=mock_storage),
        patch("app.worker.tasks.async_to_sync") as mock_async_to_sync,
        patch("app.worker.tasks.Attachment") as MockAttachment,
        patch("app.worker.tasks.fitz.open", return_value=mock_doc),
    ):

        # Configure mocks
        mock_attachment_no_uri = MagicMock()
        mock_attachment_no_uri.id = 1
        mock_attachment_no_uri.storage_uri = None
        mock_db_session.get.return_value = mock_attachment_no_uri

        # Setup async_to_sync for db.close()
        mock_async_to_sync.side_effect = lambda func: (lambda: None)

        # Call the task function directly
        result = process_pdf_attachment(attachment_id=1)

        # Verify the task returned an error message
        assert "no storage uri" in result.lower()

    # 5. Test storage.get_file returns None
    with (
        patch("app.worker.tasks.get_session", return_value=mock_db_session),
        patch("app.worker.tasks.StorageService", return_value=mock_storage),
        patch("app.worker.tasks.async_to_sync") as mock_async_to_sync,
        patch("app.worker.tasks.Attachment") as MockAttachment,
        patch("app.worker.tasks.fitz.open", return_value=mock_doc),
        patch("app.worker.tasks.process_pdf_attachment.retry") as mock_retry,
    ):

        # Configure mocks
        mock_db_session.get.return_value = mock_attachment

        # Setup async_to_sync to handle different types of calls
        def fake_async_to_sync_none(func):
            if func == mock_db_session.close:
                # For session.close(), just return a callable that does nothing
                return lambda: None
            else:
                # For other cases like storage.get_file, return None
                return lambda *args, **kwargs: None

        mock_async_to_sync.side_effect = fake_async_to_sync_none

        # Setup retry to raise a specific Celery Retry exception
        mock_retry.side_effect = Retry("Task can be retried", None)

        # Expect task to raise Retry exception if the data isn't found
        with pytest.raises(Retry):
            process_pdf_attachment(attachment_id=1)


def test_process_pdf_attachment_open_pdf():
    """Test that the task opens the PDF and gets the page count."""
    # Import the task
    from app.worker.tasks import process_pdf_attachment

    # Setup mocks
    mock_db_session = MagicMock()
    # Add a close method that can be called via async_to_sync
    mock_db_session.close = MagicMock()

    mock_attachment = MagicMock()
    mock_attachment.id = 1
    mock_attachment.storage_uri = "test-storage-uri"

    mock_storage = MagicMock()
    mock_storage_get_file = AsyncMock(return_value=b"pdfbytes")
    mock_storage.get_file = mock_storage_get_file

    # Create a mock document with page count
    mock_doc = MagicMock()
    mock_doc.page_count = 3

    # Mock fitz.open to return our mock document
    with (
        patch("app.worker.tasks.get_session", return_value=mock_db_session),
        patch("app.worker.tasks.StorageService", return_value=mock_storage),
        patch("app.worker.tasks.async_to_sync") as mock_async_to_sync,
        patch("app.worker.tasks.fitz.open", return_value=mock_doc) as mock_fitz_open,
    ):

        # Configure mocks
        mock_db_session.get.return_value = mock_attachment

        # Setup async_to_sync to handle different types of calls
        def fake_async_to_sync(func):
            if func == mock_db_session.close:
                # For session.close(), just return a callable that does nothing
                return lambda: None
            else:
                # For other cases like storage.get_file
                return lambda *args, **kwargs: b"pdfbytes"

        mock_async_to_sync.side_effect = fake_async_to_sync

        # Call the task
        result = process_pdf_attachment(attachment_id=1)

        # Verify fitz.open was called with the correct arguments
        mock_fitz_open.assert_called_once_with(stream=b"pdfbytes", filetype="pdf")

        # Verify the page count is logged (indirectly through success message)
        assert "pages: 3" in result.lower()

    # Test error when opening PDF
    with (
        patch("app.worker.tasks.get_session", return_value=mock_db_session),
        patch("app.worker.tasks.StorageService", return_value=mock_storage),
        patch("app.worker.tasks.async_to_sync") as mock_async_to_sync,
        patch(
            "app.worker.tasks.fitz.open", side_effect=Exception("PDF open error")
        ) as mock_fitz_open,
    ):

        # Configure mocks
        mock_db_session.get.return_value = mock_attachment

        # Setup async_to_sync for different function calls
        def fake_async_to_sync(func):
            if func == mock_db_session.close:
                # For session.close(), just return a callable that does nothing
                return lambda: None
            else:
                # For other cases like storage.get_file
                return lambda *args, **kwargs: b"pdfbytes"

        mock_async_to_sync.side_effect = fake_async_to_sync

        # Call the task
        result = process_pdf_attachment(attachment_id=1)

        # Verify error handling
        assert "failed to open pdf" in result.lower()


def test_process_pdf_attachment_text_extraction_and_save():  # noqa: C901
    """Test that the task extracts text from PDF pages and saves to the database."""
    # Import the task and model
    from app.models.attachment_text_content import AttachmentTextContent  # noqa: F401
    from app.worker.tasks import process_pdf_attachment

    # Setup mocks
    mock_db_session = MagicMock()
    mock_attachment = MagicMock()
    mock_attachment.id = 1
    mock_attachment.storage_uri = "test-storage-uri"

    mock_storage = MagicMock()
    mock_storage_get_file = AsyncMock(return_value=b"pdfbytes")
    mock_storage.get_file = mock_storage_get_file

    # Create mock document and pages
    mock_doc = MagicMock()
    mock_doc.page_count = 3

    # Create mock pages
    mock_pages = []
    for i in range(3):
        mock_page = MagicMock()
        mock_page.get_text.return_value = f"Text from page {i+1}"
        mock_pages.append(mock_page)

    # Make doc.load_page return the appropriate mock page
    mock_doc.load_page = lambda page_num: mock_pages[page_num]

    # Test single transaction mode
    with (
        patch("app.worker.tasks.get_session", return_value=mock_db_session),
        patch("app.worker.tasks.StorageService", return_value=mock_storage),
        patch("app.worker.tasks.async_to_sync") as mock_async_to_sync,
        patch("app.worker.tasks.fitz.open", return_value=mock_doc),
        patch("app.worker.tasks.settings.PDF_USE_SINGLE_TRANSACTION", True),
        patch("app.worker.tasks.AttachmentTextContent") as MockAttachmentTextContent,
    ):

        # Configure mocks
        mock_db_session.get.return_value = mock_attachment
        mock_db_session.close = MagicMock()
        mock_db_session.commit = MagicMock()
        mock_db_session.rollback = MagicMock()

        # Create counter functions that increment call counts when used
        commit_count = 0
        rollback_count = 0

        def fake_commit():  # noqa: F811
            nonlocal commit_count
            commit_count += 1

        def fake_rollback():  # noqa: F811
            nonlocal rollback_count
            rollback_count += 1

        def fake_async_to_sync(func):
            if func == mock_db_session.close:
                return lambda: None
            elif func == mock_db_session.commit:
                mock_db_session.commit()  # Increment the mock's call count
                return fake_commit
            elif func == mock_db_session.rollback:
                mock_db_session.rollback()  # Increment the mock's call count
                return fake_rollback
            else:
                return lambda *args, **kwargs: b"pdfbytes"

        mock_async_to_sync.side_effect = fake_async_to_sync
        mock_db_session.begin = MagicMock(
            return_value=MagicMock(__enter__=MagicMock(), __exit__=MagicMock())
        )

        # Call the task
        result = process_pdf_attachment(attachment_id=1)

        # Verify that text was extracted and saved for each page
        assert MockAttachmentTextContent.call_count == 3
        # Verify add was called for each page
        assert mock_db_session.add.call_count == 3
        # Verify begin() was called (single transaction)
        assert mock_db_session.begin.call_count == 1

        # Verify success status including page counts
        assert "pages: 3" in result.lower()
        assert "success: 3" in result.lower()

    # Test batch transaction mode
    with (
        patch("app.worker.tasks.get_session", return_value=mock_db_session),
        patch("app.worker.tasks.StorageService", return_value=mock_storage),
        patch("app.worker.tasks.async_to_sync") as mock_async_to_sync,
        patch("app.worker.tasks.fitz.open", return_value=mock_doc),
        patch("app.worker.tasks.settings.PDF_USE_SINGLE_TRANSACTION", False),
        patch("app.worker.tasks.settings.PDF_BATCH_COMMIT_SIZE", 2),
        patch("app.worker.tasks.AttachmentTextContent") as MockAttachmentTextContent,
    ):

        # Reset mock counts
        mock_db_session.reset_mock()
        MockAttachmentTextContent.reset_mock()

        # Configure mocks
        mock_db_session.get.return_value = mock_attachment
        mock_db_session.close = MagicMock()
        mock_db_session.commit = MagicMock()
        mock_db_session.rollback = MagicMock()

        # Create counter functions that increment call counts when used
        commit_count = 0
        rollback_count = 0

        def fake_commit():  # noqa: F811
            nonlocal commit_count
            commit_count += 1

        def fake_rollback():  # noqa: F811
            nonlocal rollback_count
            rollback_count += 1

        def fake_async_to_sync(func):
            if func == mock_db_session.close:
                return lambda: None
            elif func == mock_db_session.commit:
                mock_db_session.commit()  # Increment the mock's call count
                return fake_commit
            elif func == mock_db_session.rollback:
                mock_db_session.rollback()  # Increment the mock's call count
                return fake_rollback
            else:
                return lambda *args, **kwargs: b"pdfbytes"

        mock_async_to_sync.side_effect = fake_async_to_sync

        # Call the task
        result = process_pdf_attachment(attachment_id=1)

        # Verify that text was extracted and saved for each page
        assert MockAttachmentTextContent.call_count == 3
        # Verify add was called for each page
        assert mock_db_session.add.call_count == 3
        # Verify commit was called at least once (should be twice: after page 2 and after page 3)
        assert mock_db_session.commit.call_count >= 1

        # Verify success status
        assert "pages: 3" in result.lower()
        assert "success: 3" in result.lower()

    # Test error handling during page processing
    with (
        patch("app.worker.tasks.get_session", return_value=mock_db_session),
        patch("app.worker.tasks.StorageService", return_value=mock_storage),
        patch("app.worker.tasks.async_to_sync") as mock_async_to_sync,
        patch("app.worker.tasks.fitz.open", return_value=mock_doc),
        patch("app.worker.tasks.settings.PDF_USE_SINGLE_TRANSACTION", False),
        patch("app.worker.tasks.settings.PDF_BATCH_COMMIT_SIZE", 2),
        patch("app.worker.tasks.settings.PDF_MAX_ERROR_PERCENTAGE", 50.0),
        patch("app.worker.tasks.AttachmentTextContent") as MockAttachmentTextContent,
    ):

        # Reset mock counts
        mock_db_session.reset_mock()
        MockAttachmentTextContent.reset_mock()

        # Configure mocks
        mock_db_session.get.return_value = mock_attachment
        mock_db_session.close = MagicMock()
        mock_db_session.commit = MagicMock()
        mock_db_session.rollback = MagicMock()

        # Create counter functions that increment call counts when used
        commit_count = 0
        rollback_count = 0

        def fake_commit():  # noqa: F811
            nonlocal commit_count
            commit_count += 1

        def fake_rollback():  # noqa: F811
            nonlocal rollback_count
            rollback_count += 1

        def fake_async_to_sync(func):
            if func == mock_db_session.close:
                return lambda: None
            elif func == mock_db_session.commit:
                mock_db_session.commit()  # Increment the mock's call count
                return fake_commit
            elif func == mock_db_session.rollback:
                mock_db_session.rollback()  # Increment the mock's call count
                return fake_rollback
            else:
                return lambda *args, **kwargs: b"pdfbytes"

        mock_async_to_sync.side_effect = fake_async_to_sync

        # Make the second page raise an exception
        mock_pages[1].get_text.side_effect = Exception("Text extraction error")

        # Call the task
        result = process_pdf_attachment(attachment_id=1)

        # Verify rollback was called
        assert mock_db_session.rollback.call_count >= 1

        # Verify partial success status
        assert "pages: 3" in result.lower()
        assert "success: 2" in result.lower()  # 2 out of 3 pages succeeded
        assert "errors: 1" in result.lower()  # 1 page had an error
