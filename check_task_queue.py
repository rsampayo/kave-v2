#!/usr/bin/env python3
"""Debug script to check Celery task queue and test task submission."""

import logging
import sys

from celery.result import AsyncResult

from app.worker.celery_app import celery_app
from app.worker.tasks import process_pdf_attachment

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def check_task_queue():
    """Check active Celery queues and tasks."""
    logger.info("Checking Celery configuration...")
    logger.info(f"Broker URL: {celery_app.conf.broker_url}")
    logger.info(f"Result Backend: {celery_app.conf.result_backend}")

    # Check registered tasks
    logger.info("Registered tasks:")
    for task_name in sorted(celery_app.tasks.keys()):
        if not task_name.startswith("celery."):
            logger.info(f"  - {task_name}")

    # Check active queues
    try:
        active_queues = celery_app.control.inspect().active_queues()
        if active_queues:
            logger.info("Active queues:")
            for worker, queues in active_queues.items():
                logger.info(f"  Worker: {worker}")
                for queue in queues:
                    logger.info(f"    - {queue['name']}")
        else:
            logger.warning("No active queues found")
    except Exception as e:
        logger.error(f"Error inspecting queues: {e}")

    # Check scheduled tasks
    try:
        scheduled = celery_app.control.inspect().scheduled()
        if scheduled:
            logger.info("Scheduled tasks:")
            for worker, tasks in scheduled.items():
                logger.info(f"  Worker: {worker}")
                if tasks:
                    for task in tasks:
                        logger.info(
                            f"    - {task['request']['name']} (id: {task['request']['id']})"
                        )
                else:
                    logger.info("    No scheduled tasks")
        else:
            logger.info("No scheduled tasks found")
    except Exception as e:
        logger.error(f"Error inspecting scheduled tasks: {e}")


def test_task_submission(attachment_id):
    """Test submitting a task directly."""
    logger.info(f"Testing task submission for attachment_id: {attachment_id}")

    try:
        # Submit the task
        result = process_pdf_attachment.delay(attachment_id=attachment_id)
        logger.info(f"Task submitted with ID: {result.id}")

        # Check if the task was submitted correctly
        task_result = AsyncResult(result.id, app=celery_app)
        logger.info(f"Task state: {task_result.state}")

        return result.id
    except Exception as e:
        logger.error(f"Error submitting task: {e}")
        return None


if __name__ == "__main__":
    # Always check the task queue
    check_task_queue()

    # If an attachment ID is provided, test task submission
    if len(sys.argv) > 1:
        try:
            attachment_id = int(sys.argv[1])
            task_id = test_task_submission(attachment_id)
            if task_id:
                logger.info(f"Successfully submitted task with ID: {task_id}")
                logger.info(
                    f"To check task status: celery -A app.worker.celery_app result {task_id}"
                )
        except ValueError:
            logger.error(f"Invalid attachment ID: {sys.argv[1]}. Must be an integer.")
            sys.exit(1)
    else:
        logger.info("No attachment ID provided. Skipping task submission test.")
        logger.info("Usage: python check_task_queue.py <attachment_id>")
