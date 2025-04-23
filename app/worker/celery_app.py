"""Celery application configuration for asynchronous task processing."""

import logging

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

celery_app = Celery(
    "worker",
    broker=broker_url,
    backend=backend_url,
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


if __name__ == "__main__":
    # This allows running the worker directly using `python -m app.worker.celery_app worker ...`
    # Though typically you run `celery -A app.worker.celery_app worker ...`
    celery_app.start()
