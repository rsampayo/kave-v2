"""Module providing Organizations API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_active_user, get_db
from app.models.user import User
from app.schemas.organization_schemas import (
    OrganizationCreate,
    OrganizationResponse,
    OrganizationUpdate,
)
from app.services.organization_service import (
    OrganizationService,
    get_organization_service,
)

router = APIRouter()


@router.post(
    "/",
    response_model=OrganizationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new organization",
)
async def create_organization(
    data: OrganizationCreate,
    db: AsyncSession = Depends(get_db),
    service: OrganizationService = Depends(get_organization_service),
    current_user: User = Depends(get_current_active_user),
) -> OrganizationResponse:
    """Create a new organization.

    Args:
        data: Organization data
        db: Database session
        service: Organization service
        current_user: Current authenticated user

    Returns:
        OrganizationResponse: The created organization

    Raises:
        HTTPException: If an organization with the same name, webhook email,
                      or webhook secret already exists
    """
    # Check if organization with the same name already exists
    existing_org = await service.get_organization_by_name(data.name)
    if existing_org:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Organization with name {data.name!r} already exists",
        )

    # Check if organization with the same webhook email already exists
    existing_org = await service.get_organization_by_email(data.webhook_email)
    if existing_org:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Organization with webhook email {data.webhook_email!r} already exists"
            ),
        )

    # Create the organization
    organization = await service.create_organization(data)
    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        if "mandrill_webhook_secret" in str(e):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Organization with the same webhook secret already exists. "
                "This is a security risk.",
            ) from e
        raise e

    # Convert to response model
    return OrganizationResponse.model_validate(organization)


@router.get(
    "/",
    response_model=list[OrganizationResponse],
    summary="Get all organizations",
)
async def get_organizations(
    service: OrganizationService = Depends(get_organization_service),
    current_user: User = Depends(get_current_active_user),
) -> list[OrganizationResponse]:
    """Get all organizations.

    Args:
        service: Organization service
        current_user: Current authenticated user

    Returns:
        List[OrganizationResponse]: List of all organizations
    """
    organizations = await service.get_all_organizations()
    return [
        OrganizationResponse.model_validate(organization)
        for organization in organizations
    ]


@router.get(
    "/{organization_id}",
    response_model=OrganizationResponse,
    summary="Get an organization by ID",
)
async def get_organization(
    organization_id: str,
    service: OrganizationService = Depends(get_organization_service),
    current_user: User = Depends(get_current_active_user),
) -> OrganizationResponse:
    """Get an organization by ID.

    Args:
        organization_id: Organization ID (integer or UUID)
        service: Organization service
        current_user: Current authenticated user

    Returns:
        OrganizationResponse: The requested organization

    Raises:
        HTTPException: If the organization is not found
    """
    try:
        # Try to convert to integer first
        org_id = int(organization_id)
        organization = await service.get_organization_by_id(org_id)
    except ValueError as e:
        # If not a valid integer, handle as a string ID (UUID)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organization with ID {organization_id} not found",
        ) from e

    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organization with ID {organization_id} not found",
        )
    return OrganizationResponse.model_validate(organization)


@router.patch(
    "/{organization_id}",
    response_model=OrganizationResponse,
    summary="Update an organization partially",
)
async def patch_organization(
    organization_id: int,
    data: OrganizationUpdate,
    db: AsyncSession = Depends(get_db),
    service: OrganizationService = Depends(get_organization_service),
    current_user: User = Depends(get_current_active_user),
) -> OrganizationResponse:
    """Update an organization partially.

    Args:
        organization_id: Organization ID
        data: Updated organization data
        db: Database session
        service: Organization service
        current_user: Current authenticated user

    Returns:
        OrganizationResponse: The updated organization

    Raises:
        HTTPException: If the organization is not found or conflicts with existing data
    """
    # Check if organization exists
    existing_org = await service.get_organization_by_id(organization_id)
    if not existing_org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organization with ID {organization_id} not found",
        )

    # If the name is changing, check if the new name is already in use
    if data.name and data.name != existing_org.name:
        name_exists = await service.get_organization_by_name(data.name)
        if name_exists:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Organization with name {data.name!r} already exists",
            )

    # If the email is changing, check if the new email is already in use
    if data.webhook_email and data.webhook_email != existing_org.webhook_email:
        email_exists = await service.get_organization_by_email(data.webhook_email)
        if email_exists:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Organization with webhook email {data.webhook_email!r} already exists",
            )

    # Update the organization
    updated_org = await service.update_organization(organization_id, data)
    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        if "mandrill_webhook_secret" in str(e):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Organization with the same webhook secret already exists.",
            ) from e
        raise e

    return OrganizationResponse.model_validate(updated_org)


@router.delete(
    "/{organization_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an organization",
)
async def delete_organization(
    organization_id: int,
    db: AsyncSession = Depends(get_db),
    service: OrganizationService = Depends(get_organization_service),
    current_user: User = Depends(get_current_active_user),
) -> None:
    """Delete an organization.

    Args:
        organization_id: Organization ID
        db: Database session
        service: Organization service
        current_user: Current authenticated user

    Raises:
        HTTPException: If the organization is not found
    """
    # Check if organization exists
    existing_org = await service.get_organization_by_id(organization_id)
    if not existing_org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organization with ID {organization_id} not found",
        )

    # Delete the organization
    await service.delete_organization(organization_id)
    await db.commit()
