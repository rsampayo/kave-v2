"""Module providing Organization Service functionality."""

import logging

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_db
from app.models.organization import Organization
from app.schemas.organization_schemas import OrganizationCreate, OrganizationUpdate

logger = logging.getLogger(__name__)


class OrganizationService:
    """Service for managing organizations."""

    def __init__(self, db: AsyncSession):
        """Initialize the organization service.

        Args:
            db: Database session
        """
        self.db = db

    async def create_organization(self, data: OrganizationCreate) -> Organization:
        """Create a new organization.

        Args:
            data: Organization data

        Returns:
            Organization: The created organization
        """
        organization = Organization(
            name=data.name,
            webhook_email=data.webhook_email,
            mandrill_api_key=data.mandrill_api_key,
            mandrill_webhook_secret=data.mandrill_webhook_secret,
            is_active=True,
        )
        self.db.add(organization)
        await self.db.flush()
        return organization

    async def get_organization_by_id(self, organization_id: int) -> Organization | None:
        """Get an organization by ID.

        Args:
            organization_id: Organization ID

        Returns:
            Optional[Organization]: The organization if found, None otherwise
        """
        query = select(Organization).where(Organization.id == organization_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_organization_by_name(self, name: str) -> Organization | None:
        """Get an organization by name.

        Args:
            name: Organization name

        Returns:
            Optional[Organization]: The organization if found, None otherwise
        """
        query = select(Organization).where(Organization.name == name)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_organization_by_email(self, email: str) -> Organization | None:
        """Get an organization by webhook email.

        Args:
            email: Organization webhook email

        Returns:
            Optional[Organization]: The organization if found, None otherwise
        """
        query = select(Organization).where(Organization.webhook_email == email)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_organization_by_webhook_secret(
        self, secret: str
    ) -> Organization | None:
        """Get an organization by webhook secret.

        Args:
            secret: Organization webhook secret

        Returns:
            Optional[Organization]: The organization if found, None otherwise
        """
        query = select(Organization).where(
            Organization.mandrill_webhook_secret == secret
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_all_organizations(self) -> list[Organization]:
        """Get all organizations.

        Returns:
            List[Organization]: List of all organizations
        """
        query = select(Organization)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update_organization(
        self, organization_id: int, data: OrganizationUpdate
    ) -> Organization | None:
        """Update an organization.

        Args:
            organization_id: Organization ID
            data: Updated organization data

        Returns:
            Optional[Organization]: The updated organization if found, None otherwise
        """
        organization = await self.get_organization_by_id(organization_id)
        if not organization:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(organization, key, value)

        await self.db.flush()
        return organization

    async def delete_organization(self, organization_id: int) -> bool:
        """Delete an organization.

        Args:
            organization_id: Organization ID

        Returns:
            bool: True if the organization was deleted, False otherwise
        """
        organization = await self.get_organization_by_id(organization_id)
        if not organization:
            return False

        await self.db.delete(organization)
        await self.db.flush()
        return True


async def get_organization_service(
    db: AsyncSession = Depends(get_db),
) -> OrganizationService:
    """Dependency function to get the organization service.

    Args:
        db: Database session

    Returns:
        OrganizationService: The organization service
    """
    return OrganizationService(db)
