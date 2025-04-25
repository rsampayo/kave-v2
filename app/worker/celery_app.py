"""Celery application configuration for asynchronous task processing."""

import logging
import ssl
from urllib.parse import urlparse

from celery import Celery  # type: ignore

from app.core.config import settings

logger = logging.getLogger(__name__)

# Determine broker and backend URLs, prioritizing Heroku's REDIS_URL if available
broker_url = settings.REDIS_URL or settings.CELERY_BROKER_URL
backend_url = settings.REDIS_URL or settings.CELERY_RESULT_BACKEND

if settings.REDIS_URL and settings.REDIS_URL != settings.CELERY_BROKER_URL:
    logger.info(f"Using REDIS_URL from environment for Celery broker: {broker_url}")
if settings.REDIS_URL and settings.REDIS_URL != settings.CELERY_RESULT_BACKEND:
    logger.info(f"Using REDIS_URL from environment for Celery backend: {backend_url}")

# Configure Celery app - We need to handle rediss:// URLs differently
broker_scheme = urlparse(broker_url).scheme if broker_url else None
backend_scheme = urlparse(backend_url).scheme if backend_url else None

broker_options = {}
backend_options = {}

# Configure app with appropriate parameters based on URL schemes
if broker_scheme == 'rediss':
    logger.info("Configuring SSL options for secure Redis broker connection")
    # Require SSL certificate validation for the broker
    broker_options['broker_use_ssl'] = {'cert_reqs': ssl.CERT_REQUIRED}

if backend_scheme == 'rediss':
    logger.info("Configuring SSL options for secure Redis backend connection")
    # Require SSL certificate validation for the result backend
    backend_options['result_backend_use_ssl'] = {'cert_reqs': ssl.CERT_REQUIRED}

celery_app = Celery(
    "worker",
    broker=broker_url,
    backend=backend_url,
    include=["app.worker.tasks"],
    # Apply SSL options for broker and backend
    **broker_options,
    **backend_options,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Recommended Celery settings for reliability
    task_acks_late=True,
    worker_prefetch_multiplier=1,  # Process one task at a time per worker process
    broker_connection_retry_on_startup=True,  # Retry connection during startup
    broker_connection_max_retries=10,  # Maximum number of retries for broker connection
    # Broker connection timeout settings - added separately from URL
    broker_connection_timeout=10,
    # Worker recycling to prevent memory leaks
    worker_max_tasks_per_child=5,  # Restart worker process after 5 tasks to prevent memory leaks
)

logger.info(f"Celery App {celery_app.main!r} initialized.")
logger.info(f"Broker URL: {celery_app.conf.broker_url}")
logger.info(f"Result Backend: {celery_app.conf.result_backend}")

if __name__ == "__main__":
    # This allows running the worker directly using `python -m app.worker.celery_app worker ...`
    # Though typically you run `celery -A app.worker.celery_app worker ...`
    celery_app.start()
