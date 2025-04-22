"""
Helper script to run the remove_attachment_content migration.
"""

import asyncio
import logging

from app.db.session import engine
from scripts.remove_attachment_content import upgrade

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def run_migration() -> None:
    """Run the remove_attachment_content migration."""
    logger.info("Starting attachment content column migration...")
    try:
        await upgrade(engine)
        logger.info("Migration completed successfully")
    except Exception as e:
        logger.error("Migration failed: %s", str(e))
    finally:
        await engine.dispose()
        logger.info("Engine disposed")


if __name__ == "__main__":
    asyncio.run(run_migration())
