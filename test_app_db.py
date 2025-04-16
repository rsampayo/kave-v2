import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app.db.session import async_session_factory, engine
from app.services.initialization_service import InitializationService

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def test_lifespan(app: FastAPI):
    """Simplified lifespan for testing."""
    # Startup
    logger.info("Application starting up")

    # Initialize default data
    try:
        logger.info("Initializing application data")
        async with async_session_factory() as db:
            init_service = InitializationService(db)
            await init_service.initialize()
            logger.info("Application data initialization completed")
    except Exception as e:
        logger.error(f"Failed to initialize application data: {str(e)}")

    yield

    # Shutdown
    logger.info("Application shutdown")
    await engine.dispose()


async def main():
    """Test the application database connection."""
    app = FastAPI()

    try:
        # Simulate the lifespan context
        async with test_lifespan(app):
            logger.info("Inside lifespan context - application is running")

            # Try a simple database operation
            async with async_session_factory() as session:
                result = await session.execute(text("SELECT 1"))
                value = result.scalar()
                logger.info(f"Database query result: {value}")
    except Exception as e:
        logger.error(f"Error in main function: {e}")


if __name__ == "__main__":
    asyncio.run(main())
