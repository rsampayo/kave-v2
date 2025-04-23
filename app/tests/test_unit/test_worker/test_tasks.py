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

    # 2. Test successful data fetching
    with (
        patch("app.worker.tasks.get_session", return_value=mock_db_session),
        patch("app.worker.tasks.StorageService", return_value=mock_storage),
        patch("app.worker.tasks.async_to_sync") as mock_async_to_sync,
        patch("app.worker.tasks.Attachment") as MockAttachment,
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
        assert "Successfully fetched data" in result

    # 3. Test attachment not found
    with (
        patch("app.worker.tasks.get_session", return_value=mock_db_session),
        patch("app.worker.tasks.StorageService", return_value=mock_storage),
        patch("app.worker.tasks.async_to_sync") as mock_async_to_sync,
        patch("app.worker.tasks.Attachment") as MockAttachment,
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
