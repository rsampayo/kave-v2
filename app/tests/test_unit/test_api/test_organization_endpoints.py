"""Tests for the organization endpoints."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError

from app.api.v1.endpoints.organizations import (
    create_organization,
    delete_organization,
    get_organization,
    get_organizations,
    patch_organization,
)
from app.models.organization import Organization
from app.schemas.organization_schemas import OrganizationCreate, OrganizationUpdate


@pytest.fixture
def mock_organization():
    """Create a mock organization."""
    return Organization(
        id=1,
        name="Test Organization",
        webhook_email="webhook@example.com",
        mandrill_api_key="test_api_key",
        mandrill_webhook_secret="test_webhook_secret",
        is_active=True,
    )


@pytest.fixture
def mock_organization_service(mock_organization):
    """Create a mock organization service."""
    service = MagicMock()
    # Use AsyncMock for async methods
    service.get_organization_by_id = AsyncMock(return_value=mock_organization)
    service.get_organization_by_name = AsyncMock(return_value=None)
    service.get_organization_by_email = AsyncMock(return_value=None)
    service.get_all_organizations = AsyncMock(return_value=[mock_organization])
    service.create_organization = AsyncMock(return_value=mock_organization)
    service.update_organization = AsyncMock(return_value=mock_organization)
    service.delete_organization = AsyncMock(return_value=True)
    return service


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    db = MagicMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    return db


@pytest.fixture
def organization_create():
    """Create an organization creation data object."""
    return OrganizationCreate(
        name="Test Organization",
        webhook_email="webhook@example.com",
        mandrill_api_key="test_api_key",
        mandrill_webhook_secret="test_webhook_secret",
    )


@pytest.fixture
def organization_update():
    """Create an organization update data object."""
    return OrganizationUpdate(
        name="Updated Organization",
        webhook_email="updated@example.com",
        mandrill_api_key="updated_api_key",
        mandrill_webhook_secret="updated_webhook_secret",
        is_active=True,
    )


@pytest.mark.asyncio
async def test_create_organization_success(
    mock_db, mock_organization_service, organization_create, mock_organization
) -> None:
    """Test successful organization creation."""
    # Arrange
    current_user = MagicMock()

    # Act
    result = await create_organization(
        data=organization_create,
        db=mock_db,
        service=mock_organization_service,
        current_user=current_user,
    )

    # Assert
    mock_organization_service.get_organization_by_name.assert_called_once_with(
        organization_create.name
    )
    mock_organization_service.get_organization_by_email.assert_called_once_with(
        organization_create.webhook_email
    )
    mock_organization_service.create_organization.assert_called_once_with(
        organization_create
    )
    mock_db.commit.assert_called_once()
    assert result.id == mock_organization.id
    assert result.name == mock_organization.name
    assert result.webhook_email == mock_organization.webhook_email


@pytest.mark.asyncio
async def test_create_organization_name_exists(
    mock_db, mock_organization_service, organization_create, mock_organization
) -> None:
    """Test organization creation with existing name."""
    # Arrange
    current_user = MagicMock()
    mock_organization_service.get_organization_by_name = AsyncMock(
        return_value=mock_organization
    )

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await create_organization(
            data=organization_create,
            db=mock_db,
            service=mock_organization_service,
            current_user=current_user,
        )

    assert exc_info.value.status_code == status.HTTP_409_CONFLICT
    assert f"Organization with name {organization_create.name!r} already exists" in str(
        exc_info.value.detail
    )
    mock_organization_service.create_organization.assert_not_called()
    mock_db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_create_organization_email_exists(
    mock_db, mock_organization_service, organization_create, mock_organization
) -> None:
    """Test organization creation with existing email."""
    # Arrange
    current_user = MagicMock()
    mock_organization_service.get_organization_by_name = AsyncMock(return_value=None)
    mock_organization_service.get_organization_by_email = AsyncMock(
        return_value=mock_organization
    )

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await create_organization(
            data=organization_create,
            db=mock_db,
            service=mock_organization_service,
            current_user=current_user,
        )

    assert exc_info.value.status_code == status.HTTP_409_CONFLICT
    assert (
        f"Organization with webhook email {organization_create.webhook_email!r} already exists"
        in str(exc_info.value.detail)
    )
    mock_organization_service.create_organization.assert_not_called()
    mock_db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_create_organization_integrity_error(
    mock_db, mock_organization_service, organization_create
) -> None:
    """Test organization creation with integrity error."""
    # Arrange
    current_user = MagicMock()
    mock_db.commit.side_effect = IntegrityError(
        "mandrill_webhook_secret",
        {"stmt": "mock statement"},
        Exception("mock exception"),
    )

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await create_organization(
            data=organization_create,
            db=mock_db,
            service=mock_organization_service,
            current_user=current_user,
        )

    assert exc_info.value.status_code == status.HTTP_409_CONFLICT
    assert "Organization with the same webhook secret already exists" in str(
        exc_info.value.detail
    )
    mock_db.rollback.assert_called_once()


@pytest.mark.asyncio
async def test_create_organization_other_integrity_error(
    mock_db, mock_organization_service, organization_create
) -> None:
    """Test organization creation with other integrity error."""
    # Arrange
    current_user = MagicMock()
    mock_db.commit.side_effect = IntegrityError(
        "other constraint", {"stmt": "mock statement"}, Exception("mock exception")
    )

    # Act & Assert
    with pytest.raises(IntegrityError):
        await create_organization(
            data=organization_create,
            db=mock_db,
            service=mock_organization_service,
            current_user=current_user,
        )

    mock_db.rollback.assert_called_once()


@pytest.mark.asyncio
async def test_get_organizations(mock_organization_service, mock_organization) -> None:
    """Test getting all organizations."""
    # Arrange
    current_user = MagicMock()

    # Act
    result = await get_organizations(
        service=mock_organization_service,
        current_user=current_user,
    )

    # Assert
    mock_organization_service.get_all_organizations.assert_called_once()
    assert len(result) == 1
    assert result[0].id == mock_organization.id
    assert result[0].name == mock_organization.name


@pytest.mark.asyncio
async def test_get_organization_success(
    mock_organization_service, mock_organization
) -> None:
    """Test getting an organization by ID."""
    # Arrange
    current_user = MagicMock()
    organization_id = "1"  # String ID to test conversion

    # Act
    result = await get_organization(
        organization_id=organization_id,
        service=mock_organization_service,
        current_user=current_user,
    )

    # Assert
    mock_organization_service.get_organization_by_id.assert_called_once_with(1)
    assert result.id == mock_organization.id
    assert result.name == mock_organization.name


@pytest.mark.asyncio
async def test_get_organization_not_found(mock_organization_service) -> None:
    """Test getting a non-existent organization."""
    # Arrange
    current_user = MagicMock()
    organization_id = "1"
    mock_organization_service.get_organization_by_id = AsyncMock(return_value=None)

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await get_organization(
            organization_id=organization_id,
            service=mock_organization_service,
            current_user=current_user,
        )

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
    assert f"Organization with ID {organization_id} not found" in str(
        exc_info.value.detail
    )


@pytest.mark.asyncio
async def test_get_organization_invalid_id(mock_organization_service) -> None:
    """Test getting an organization with invalid ID format."""
    # Arrange
    current_user = MagicMock()
    organization_id = "invalid-id"

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await get_organization(
            organization_id=organization_id,
            service=mock_organization_service,
            current_user=current_user,
        )

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
    assert f"Organization with ID {organization_id} not found" in str(
        exc_info.value.detail
    )


@pytest.mark.asyncio
async def test_patch_organization_success(
    mock_db, mock_organization_service, organization_update, mock_organization
) -> None:
    """Test successful organization update."""
    # Arrange
    current_user = MagicMock()
    organization_id = 1

    # Act
    result = await patch_organization(
        organization_id=organization_id,
        data=organization_update,
        db=mock_db,
        service=mock_organization_service,
        current_user=current_user,
    )

    # Assert
    mock_organization_service.get_organization_by_id.assert_called_once_with(
        organization_id
    )
    mock_organization_service.update_organization.assert_called_once_with(
        organization_id, organization_update
    )
    mock_db.commit.assert_called_once()
    assert result.id == mock_organization.id
    assert result.name == mock_organization.name


@pytest.mark.asyncio
async def test_patch_organization_not_found(
    mock_db, mock_organization_service, organization_update
) -> None:
    """Test updating a non-existent organization."""
    # Arrange
    current_user = MagicMock()
    organization_id = 1
    mock_organization_service.get_organization_by_id = AsyncMock(return_value=None)

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await patch_organization(
            organization_id=organization_id,
            data=organization_update,
            db=mock_db,
            service=mock_organization_service,
            current_user=current_user,
        )

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
    assert f"Organization with ID {organization_id} not found" in str(
        exc_info.value.detail
    )
    mock_organization_service.update_organization.assert_not_called()
    mock_db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_patch_organization_name_conflict(
    mock_db, mock_organization_service, organization_update, mock_organization
) -> None:
    """Test organization update with name conflict."""
    # Arrange
    current_user = MagicMock()
    organization_id = 1
    conflicting_org = Organization(
        id=2,
        name="Updated Organization",
        webhook_email="other@example.com",
        mandrill_api_key="other_api_key",
        mandrill_webhook_secret="other_webhook_secret",
        is_active=True,
    )
    mock_organization_service.get_organization_by_name = AsyncMock(
        return_value=conflicting_org
    )

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await patch_organization(
            organization_id=organization_id,
            data=organization_update,
            db=mock_db,
            service=mock_organization_service,
            current_user=current_user,
        )

    assert exc_info.value.status_code == status.HTTP_409_CONFLICT
    assert f"Organization with name {organization_update.name!r} already exists" in str(
        exc_info.value.detail
    )
    mock_organization_service.update_organization.assert_not_called()
    mock_db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_patch_organization_email_conflict(
    mock_db, mock_organization_service, organization_update, mock_organization
) -> None:
    """Test organization update with email conflict."""
    # Arrange
    current_user = MagicMock()
    organization_id = 1
    mock_organization_service.get_organization_by_name = AsyncMock(return_value=None)
    conflicting_org = Organization(
        id=2,
        name="Other Organization",
        webhook_email="updated@example.com",
        mandrill_api_key="other_api_key",
        mandrill_webhook_secret="other_webhook_secret",
        is_active=True,
    )
    mock_organization_service.get_organization_by_email = AsyncMock(
        return_value=conflicting_org
    )

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await patch_organization(
            organization_id=organization_id,
            data=organization_update,
            db=mock_db,
            service=mock_organization_service,
            current_user=current_user,
        )

    assert exc_info.value.status_code == status.HTTP_409_CONFLICT
    assert (
        f"Organization with webhook email {organization_update.webhook_email!r} already exists"
        in str(exc_info.value.detail)
    )
    mock_organization_service.update_organization.assert_not_called()
    mock_db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_patch_organization_integrity_error(
    mock_db, mock_organization_service, organization_update, mock_organization
) -> None:
    """Test organization update with integrity error."""
    # Arrange
    current_user = MagicMock()
    organization_id = 1
    mock_db.commit.side_effect = IntegrityError(
        "mandrill_webhook_secret",
        {"stmt": "mock statement"},
        Exception("mock exception"),
    )

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await patch_organization(
            organization_id=organization_id,
            data=organization_update,
            db=mock_db,
            service=mock_organization_service,
            current_user=current_user,
        )

    assert exc_info.value.status_code == status.HTTP_409_CONFLICT
    assert "Organization with the same webhook secret already exists" in str(
        exc_info.value.detail
    )
    mock_db.rollback.assert_called_once()


@pytest.mark.asyncio
async def test_patch_organization_other_integrity_error(
    mock_db, mock_organization_service, organization_update, mock_organization
) -> None:
    """Test organization update with other integrity error."""
    # Arrange
    current_user = MagicMock()
    organization_id = 1
    mock_db.commit.side_effect = IntegrityError(
        "other constraint", {"stmt": "mock statement"}, Exception("mock exception")
    )

    # Act & Assert
    with pytest.raises(IntegrityError):
        await patch_organization(
            organization_id=organization_id,
            data=organization_update,
            db=mock_db,
            service=mock_organization_service,
            current_user=current_user,
        )

    mock_db.rollback.assert_called_once()


@pytest.mark.asyncio
async def test_delete_organization_success(
    mock_db, mock_organization_service, mock_organization
) -> None:
    """Test successful organization deletion."""
    # Arrange
    current_user = MagicMock()
    organization_id = 1

    # Act
    await delete_organization(
        organization_id=organization_id,
        db=mock_db,
        service=mock_organization_service,
        current_user=current_user,
    )

    # Assert
    mock_organization_service.get_organization_by_id.assert_called_once_with(
        organization_id
    )
    mock_organization_service.delete_organization.assert_called_once_with(
        organization_id
    )
    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_delete_organization_not_found(
    mock_db, mock_organization_service
) -> None:
    """Test deleting a non-existent organization."""
    # Arrange
    current_user = MagicMock()
    organization_id = 1
    mock_organization_service.get_organization_by_id = AsyncMock(return_value=None)

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await delete_organization(
            organization_id=organization_id,
            db=mock_db,
            service=mock_organization_service,
            current_user=current_user,
        )

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
    assert f"Organization with ID {organization_id} not found" in str(
        exc_info.value.detail
    )
    mock_organization_service.delete_organization.assert_not_called()
    mock_db.commit.assert_not_called()
