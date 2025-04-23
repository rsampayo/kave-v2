"""Tests for the Celery application configuration."""

import pytest
from celery import Celery  # type: ignore


def test_celery_app_instance():
    """Test that the Celery app instance can be created."""
    try:
        # Ensure celery_app can be imported after configuration
        from app.worker.celery_app import celery_app

        assert isinstance(celery_app, Celery)
        # Check if broker URL is configured (optional but good)
        assert celery_app.conf.broker_url is not None
    except ImportError:
        pytest.fail("Could not import celery_app from app.worker.celery_app")
    except Exception as e:
        pytest.fail(f"Failed to create celery_app instance: {e}")
