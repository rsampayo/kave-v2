"""Service for initializing application data."""

import logging
import os
from typing import Optional

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps.database import get_db
from app.core.config import settings
from app.models.organization import Organization
from app.models.user import User
from app.schemas.auth_schemas import UserCreate
from app.schemas.organization_schemas import OrganizationCreate
from app.services.organization_service import OrganizationService
from app.services.user_service import UserService

logger = logging.getLogger(__name__)


class InitializationService:
    """Service for initializing application data.

    This service handles the creation of default records needed by the application
    during startup, such as the default organization.
    """

    def __init__(self, db: AsyncSession):
        """Initialize the service.

        Args:
            db: Database session
        """
        self.db = db
        self.organization_service = OrganizationService(db)
        self.user_service = UserService(db)

    async def initialize_default_organization(self) -> Optional[Organization]:
        """Create the default organization if it doesn't exist.

        Returns:
            Optional[Organization]: The created or existing organization
        """
        # Check if we already have an organization with the configured name
        default_org = await self.organization_service.get_organization_by_name(
            settings.DEFAULT_ORGANIZATION_NAME
        )

        if default_org:
            logger.info(
                "Default organization already exists: %s",
                settings.DEFAULT_ORGANIZATION_NAME,
            )
            return default_org

        logger.info(
            "Creating default organization: %s", settings.DEFAULT_ORGANIZATION_NAME
        )

        # Create a default organization
        org_data = OrganizationCreate(
            name=settings.DEFAULT_ORGANIZATION_NAME,
            webhook_email=settings.DEFAULT_ORGANIZATION_EMAIL,
            mandrill_api_key=settings.MAILCHIMP_API_KEY,
            mandrill_webhook_secret=settings.MAILCHIMP_WEBHOOK_SECRET,
        )

        try:
            new_org = await self.organization_service.create_organization(org_data)
            await self.db.commit()
            logger.info(
                "Default organization created: %s (ID: %d)",
                new_org.name,
                new_org.id,
            )
            return new_org
        except Exception as e:
            await self.db.rollback()
            logger.error("Failed to create default organization: %s", str(e))
            return None

    async def initialize_first_superuser(self) -> None:
        """Create the first superuser if credentials are provided in settings.

        This will only create the user if all required credentials are provided
        in the application settings and no user with the same username exists.
        """
        # Check if superuser credentials are provided in settings
        if not all(
            [
                settings.FIRST_SUPERUSER_USERNAME,
                settings.FIRST_SUPERUSER_EMAIL,
                settings.FIRST_SUPERUSER_PASSWORD,
            ]
        ):
            logger.info(
                "First superuser credentials not provided in settings. Skipping."
            )
            return

        # Check if user already exists
        existing_user = await self.user_service.get_user_by_username(
            settings.FIRST_SUPERUSER_USERNAME
        )

        if existing_user:
            logger.info(
                "Superuser already exists: %s", settings.FIRST_SUPERUSER_USERNAME
            )
            return

        logger.info("Creating first superuser: %s", settings.FIRST_SUPERUSER_USERNAME)

        # Create user data
        user_data = UserCreate(
            username=settings.FIRST_SUPERUSER_USERNAME,
            email=settings.FIRST_SUPERUSER_EMAIL,
            password=settings.FIRST_SUPERUSER_PASSWORD,
            is_superuser=True,
        )

        try:
            new_user = await self.user_service.create_user(user_data)
            await self.db.commit()
            logger.info(
                "First superuser created: %s (ID: %d)",
                new_user.username,
                new_user.id,
            )
        except Exception as e:
            await self.db.rollback()
            logger.error("Failed to create first superuser: %s", str(e))

    async def _create_default_admin_user(self, db: AsyncSession) -> User:
        """Create the default admin user if it doesn't exist.

        Args:
            db: Database session

        Returns:
            User: The admin user
        """
        logger.info("Checking for default admin user")

        # Use environment variables or fall back to default values
        admin_username = os.environ.get("ADMIN_USERNAME", "admin")
        admin_password = os.environ.get("ADMIN_PASSWORD", "admin")
        admin_email = os.environ.get("ADMIN_EMAIL", "admin@example.com")

        # Use a default username if environment variable is not set
        if not admin_username:
            admin_username = "admin"

        # Ensure admin_username is treated as a string
        admin_username_str: str = str(admin_username)

        # Check if default admin exists
        user_service = UserService(db=db)
        existing_user = await user_service.get_user_by_username(admin_username_str)  # type: ignore

        if existing_user:
            logger.info(f"Default admin user '{admin_username_str}' already exists")
            return existing_user

        # Create admin user
        logger.info(f"Creating default admin user '{admin_username_str}'")
        user_data = UserCreate(
            username=admin_username_str,
            email=admin_email,
            password=admin_password,
            full_name="System Administrator",
            is_active=True,
            is_superuser=True,
        )
        admin_user = await user_service.create_user(user_data)
        logger.info(f"Created default admin user with ID {admin_user.id}")

        return admin_user

    async def initialize(self) -> None:
        """Run all initialization functions.

        This is the main method to call during application startup.
        """
        await self.initialize_default_organization()
        await self.initialize_first_superuser()
        await self._create_default_admin_user(self.db)


async def get_initialization_service(
    db: AsyncSession = Depends(get_db),
) -> InitializationService:
    """Dependency function to get the initialization service.

    Args:
        db: Database session

    Returns:
        InitializationService: The initialization service
    """
    return InitializationService(db)
