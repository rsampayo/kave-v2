"""Unit tests for Celery tasks in the worker module."""

import pytest
from unittest.mock import patch


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
