"""Module providing Initialization Service functionality."""

import logging
from typing import Optional

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_db
from app.core.config import settings
from app.models.organization import Organization
from app.schemas.organization_schemas import OrganizationCreate
from app.services.organization_service import (
    OrganizationService,
    get_organization_service,
)

logger = logging.getLogger(__name__)


class InitializationService:
    """Service responsible for initializing default data."""

    def __init__(self, db: AsyncSession, org_service: OrganizationService):
        """Initialize the initialization service.

        Args:
            db: Database session
            org_service: Organization service
        """
        self.db = db
        self.org_service = org_service

    async def init_default_organization(self) -> Optional[Organization]:
        """Initialize the default organization.

        This creates a default organization using the values from environment variables
        if no organization exists yet.

        Returns:
            Optional[Organization]: The default organization if created or exists
        """
        # Check if any organization exists
        organizations = await self.org_service.get_all_organizations()
        if organizations:
            logger.info(
                "Organizations already exist, skipping default organization creation"
            )
            return organizations[0]

        # Create default organization using environment variables
        logger.info("Creating default organization")
        default_org_data = OrganizationCreate(
            name=settings.DEFAULT_ORGANIZATION_NAME,
            webhook_email=settings.DEFAULT_ORGANIZATION_EMAIL,
            mandrill_api_key=settings.MAILCHIMP_API_KEY,
            mandrill_webhook_secret=settings.MAILCHIMP_WEBHOOK_SECRET,
        )

        # Create the organization
        try:
            organization = await self.org_service.create_organization(default_org_data)
            await self.db.commit()
            logger.info(f"Default organization created: {organization.name}")
            return organization
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to create default organization: {str(e)}")
            return None


async def get_initialization_service(
    db: AsyncSession = Depends(get_db),
    org_service: OrganizationService = Depends(get_organization_service),
) -> InitializationService:
    """Dependency function to get the initialization service.

    Args:
        db: Database session
        org_service: Organization service

    Returns:
        InitializationService: The initialization service
    """
    return InitializationService(db, org_service)
