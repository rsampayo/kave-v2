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

# Configure SSL options for secure Redis connections
broker_options = {}
backend_options = {}

# Check if Redis URL uses secure connection (rediss://)
if broker_url and urlparse(broker_url).scheme == 'rediss':
    broker_options = {
        'ssl_cert_reqs': ssl.CERT_NONE
    }
    logger.info("Configuring SSL options for secure Redis broker connection")

if backend_url and urlparse(backend_url).scheme == 'rediss':
    backend_options = {
        'ssl_cert_reqs': ssl.CERT_NONE
    }
    logger.info("Configuring SSL options for secure Redis backend connection")

celery_app = Celery(
    "worker",
    broker=broker_url,
    backend=backend_url,
    broker_transport_options=broker_options,
    redis_backend_transport_options=backend_options,
    include=["app.worker.tasks"],
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
)

logger.info(f"Celery App {celery_app.main!r} initialized.")
logger.info(f"Broker URL: {celery_app.conf.broker_url}")
logger.info(f"Result Backend: {celery_app.conf.result_backend}")
if broker_options:
    logger.info(f"Broker SSL options: {broker_options}")
if backend_options:
    logger.info(f"Backend SSL options: {backend_options}")


if __name__ == "__main__":
    # This allows running the worker directly using `python -m app.worker.celery_app worker ...`
    # Though typically you run `celery -A app.worker.celery_app worker ...`
    celery_app.start()
