"""Tests for the organization service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization
from app.schemas.organization_schemas import OrganizationCreate, OrganizationUpdate
from app.services.organization_service import (
    OrganizationService,
    get_organization_service,
)


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    db = AsyncMock(spec=AsyncSession)
    return db


@pytest.fixture
def organization_service(mock_db):
    """Create an organization service with a mock database."""
    return OrganizationService(db=mock_db)


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
async def test_create_organization(
    organization_service, organization_create, mock_db
) -> None:
    """Test organization creation."""
    # Act
    result = await organization_service.create_organization(organization_create)

    # Assert
    assert result.name == organization_create.name
    assert result.webhook_email == organization_create.webhook_email
    assert result.mandrill_api_key == organization_create.mandrill_api_key
    assert result.mandrill_webhook_secret == organization_create.mandrill_webhook_secret
    assert result.is_active is True
    mock_db.add.assert_called_once()
    mock_db.flush.assert_called_once()


@pytest.mark.asyncio
async def test_get_organization_by_id(
    organization_service, mock_organization, mock_db
) -> None:
    """Test getting an organization by ID."""
    # Arrange
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = mock_organization
    mock_db.execute.return_value = execute_result

    # Act
    result = await organization_service.get_organization_by_id(1)

    # Assert
    assert result == mock_organization
    mock_db.execute.assert_called_once()


@pytest.mark.asyncio
async def test_get_organization_by_id_not_found(organization_service, mock_db) -> None:
    """Test getting a non-existent organization by ID."""
    # Arrange
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = execute_result

    # Act
    result = await organization_service.get_organization_by_id(999)

    # Assert
    assert result is None
    mock_db.execute.assert_called_once()


@pytest.mark.asyncio
async def test_get_organization_by_name(
    organization_service, mock_organization, mock_db
) -> None:
    """Test getting an organization by name."""
    # Arrange
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = mock_organization
    mock_db.execute.return_value = execute_result

    # Act
    result = await organization_service.get_organization_by_name("Test Organization")

    # Assert
    assert result == mock_organization
    mock_db.execute.assert_called_once()


@pytest.mark.asyncio
async def test_get_organization_by_name_not_found(
    organization_service, mock_db
) -> None:
    """Test getting a non-existent organization by name."""
    # Arrange
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = execute_result

    # Act
    result = await organization_service.get_organization_by_name(
        "Nonexistent Organization"
    )

    # Assert
    assert result is None
    mock_db.execute.assert_called_once()


@pytest.mark.asyncio
async def test_get_organization_by_email(
    organization_service, mock_organization, mock_db
) -> None:
    """Test getting an organization by webhook email."""
    # Arrange
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = mock_organization
    mock_db.execute.return_value = execute_result

    # Act
    result = await organization_service.get_organization_by_email("webhook@example.com")

    # Assert
    assert result == mock_organization
    mock_db.execute.assert_called_once()


@pytest.mark.asyncio
async def test_get_organization_by_email_not_found(
    organization_service, mock_db
) -> None:
    """Test getting a non-existent organization by webhook email."""
    # Arrange
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = execute_result

    # Act
    result = await organization_service.get_organization_by_email(
        "nonexistent@example.com"
    )

    # Assert
    assert result is None
    mock_db.execute.assert_called_once()


@pytest.mark.asyncio
async def test_get_organization_by_webhook_secret(
    organization_service, mock_organization, mock_db
) -> None:
    """Test getting an organization by webhook secret."""
    # Arrange
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = mock_organization
    mock_db.execute.return_value = execute_result

    # Act
    result = await organization_service.get_organization_by_webhook_secret(
        "test_webhook_secret"
    )

    # Assert
    assert result == mock_organization
    mock_db.execute.assert_called_once()


@pytest.mark.asyncio
async def test_get_organization_by_webhook_secret_not_found(
    organization_service, mock_db
) -> None:
    """Test getting a non-existent organization by webhook secret."""
    # Arrange
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = execute_result

    # Act
    result = await organization_service.get_organization_by_webhook_secret(
        "nonexistent_secret"
    )

    # Assert
    assert result is None
    mock_db.execute.assert_called_once()


@pytest.mark.asyncio
async def test_get_all_organizations(
    organization_service, mock_organization, mock_db
) -> None:
    """Test getting all organizations."""
    # Arrange
    execute_result = MagicMock()
    scalars_result = MagicMock()
    scalars_result.all.return_value = [mock_organization]
    execute_result.scalars.return_value = scalars_result
    mock_db.execute.return_value = execute_result

    # Act
    result = await organization_service.get_all_organizations()

    # Assert
    assert len(result) == 1
    assert result[0] == mock_organization
    mock_db.execute.assert_called_once()


@pytest.mark.asyncio
async def test_update_organization(
    organization_service, mock_organization, organization_update, mock_db
) -> None:
    """Test updating an organization."""
    # Arrange
    with patch.object(
        organization_service, "get_organization_by_id", return_value=mock_organization
    ) as mock_get:
        # Act
        result = await organization_service.update_organization(1, organization_update)

        # Assert
        assert result == mock_organization
        mock_get.assert_called_once_with(1)
        assert result.name == organization_update.name
        assert result.webhook_email == organization_update.webhook_email
        assert result.mandrill_api_key == organization_update.mandrill_api_key
        assert (
            result.mandrill_webhook_secret
            == organization_update.mandrill_webhook_secret
        )
        assert result.is_active == organization_update.is_active
        mock_db.flush.assert_called_once()


@pytest.mark.asyncio
async def test_update_organization_partial(
    organization_service, mock_organization, mock_db
) -> None:
    """Test partially updating an organization."""
    # Arrange
    partial_update = OrganizationUpdate(name="Updated Organization")
    with patch.object(
        organization_service, "get_organization_by_id", return_value=mock_organization
    ) as mock_get:
        # Act
        result = await organization_service.update_organization(1, partial_update)

        # Assert
        assert result == mock_organization
        mock_get.assert_called_once_with(1)
        assert result.name == partial_update.name
        # Other fields should remain unchanged
        assert result.webhook_email == mock_organization.webhook_email
        assert result.mandrill_api_key == mock_organization.mandrill_api_key
        assert (
            result.mandrill_webhook_secret == mock_organization.mandrill_webhook_secret
        )
        assert result.is_active == mock_organization.is_active
        mock_db.flush.assert_called_once()


@pytest.mark.asyncio
async def test_update_organization_not_found(
    organization_service, organization_update, mock_db
) -> None:
    """Test updating a non-existent organization."""
    # Arrange
    with patch.object(
        organization_service, "get_organization_by_id", return_value=None
    ) as mock_get:
        # Act
        result = await organization_service.update_organization(
            999, organization_update
        )

        # Assert
        assert result is None
        mock_get.assert_called_once_with(999)
        mock_db.flush.assert_not_called()


@pytest.mark.asyncio
async def test_delete_organization(
    organization_service, mock_organization, mock_db
) -> None:
    """Test deleting an organization."""
    # Arrange
    with patch.object(
        organization_service, "get_organization_by_id", return_value=mock_organization
    ) as mock_get:
        # Act
        result = await organization_service.delete_organization(1)

        # Assert
        assert result is True
        mock_get.assert_called_once_with(1)
        mock_db.delete.assert_called_once_with(mock_organization)
        mock_db.flush.assert_called_once()


@pytest.mark.asyncio
async def test_delete_organization_not_found(organization_service, mock_db) -> None:
    """Test deleting a non-existent organization."""
    # Arrange
    with patch.object(
        organization_service, "get_organization_by_id", return_value=None
    ) as mock_get:
        # Act
        result = await organization_service.delete_organization(999)

        # Assert
        assert result is False
        mock_get.assert_called_once_with(999)
        mock_db.delete.assert_not_called()
        mock_db.flush.assert_not_called()


@pytest.mark.asyncio
async def test_get_organization_service(mock_db) -> None:
    """Test the get_organization_service dependency."""
    # Act
    service = await get_organization_service(mock_db)

    # Assert
    assert isinstance(service, OrganizationService)
    assert service.db == mock_db
