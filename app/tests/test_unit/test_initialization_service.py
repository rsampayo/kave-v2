"""Unit tests for the initialization service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.organization import Organization
from app.models.user import User
from app.schemas.auth_schemas import UserCreate
from app.schemas.organization_schemas import OrganizationCreate
from app.services.initialization_service import InitializationService
from app.services.organization_service import OrganizationService
from app.services.user_service import UserService


@pytest.mark.asyncio
async def test_initialize_default_organization_when_not_exists(
    db_session: AsyncSession,
):
    """Test creating default organization when it doesn't exist."""
    # Arrange
    org_service_mock = AsyncMock(spec=OrganizationService)
    org_service_mock.get_organization_by_name.return_value = None

    # Create a new organization when create_organization is called
    org = Organization(
        id=1,
        name=settings.DEFAULT_ORGANIZATION_NAME,
        webhook_email=settings.DEFAULT_ORGANIZATION_EMAIL,
    )
    org_service_mock.create_organization.return_value = org

    # Create service with mocked dependencies
    init_service = InitializationService(db_session)
    init_service.organization_service = org_service_mock

    # Act
    result = await init_service.initialize_default_organization()

    # Assert
    assert result is not None
    assert result.id == 1
    assert result.name == settings.DEFAULT_ORGANIZATION_NAME
    org_service_mock.get_organization_by_name.assert_called_once_with(
        settings.DEFAULT_ORGANIZATION_NAME
    )
    org_service_mock.create_organization.assert_called_once()
    create_args = org_service_mock.create_organization.call_args.args[0]
    assert isinstance(create_args, OrganizationCreate)
    assert create_args.name == settings.DEFAULT_ORGANIZATION_NAME
    assert create_args.webhook_email == settings.DEFAULT_ORGANIZATION_EMAIL


@pytest.mark.asyncio
async def test_initialize_default_organization_when_exists(db_session: AsyncSession):
    """Test that existing default organization is returned and not recreated."""
    # Arrange
    existing_org = Organization(
        id=1,
        name=settings.DEFAULT_ORGANIZATION_NAME,
        webhook_email=settings.DEFAULT_ORGANIZATION_EMAIL,
    )

    org_service_mock = AsyncMock(spec=OrganizationService)
    org_service_mock.get_organization_by_name.return_value = existing_org

    # Create service with mocked dependencies
    init_service = InitializationService(db_session)
    init_service.organization_service = org_service_mock

    # Act
    result = await init_service.initialize_default_organization()

    # Assert
    assert result is existing_org
    org_service_mock.get_organization_by_name.assert_called_once_with(
        settings.DEFAULT_ORGANIZATION_NAME
    )
    org_service_mock.create_organization.assert_not_called()


@pytest.mark.asyncio
async def test_initialize_default_organization_error_handling(db_session: AsyncSession):
    """Test error handling when creating default organization fails."""
    # Arrange
    org_service_mock = AsyncMock(spec=OrganizationService)
    org_service_mock.get_organization_by_name.return_value = None
    org_service_mock.create_organization.side_effect = Exception("Database error")

    db_session_mock = AsyncMock(spec=AsyncSession)

    # Create service with mocked dependencies
    init_service = InitializationService(db_session_mock)
    init_service.organization_service = org_service_mock
    init_service.db = db_session_mock

    # Act
    result = await init_service.initialize_default_organization()

    # Assert
    assert result is None
    db_session_mock.rollback.assert_called_once()


@pytest.mark.asyncio
async def test_initialize_first_superuser_when_credentials_missing(
    db_session: AsyncSession,
):
    """Test that superuser creation is skipped when credentials are missing."""
    # Arrange
    user_service_mock = AsyncMock(spec=UserService)

    # Create service with mocked dependencies
    init_service = InitializationService(db_session)
    init_service.user_service = user_service_mock

    # Act - using patch to temporarily set credentials to None
    with patch("app.core.config.settings.FIRST_SUPERUSER_USERNAME", None):
        await init_service.initialize_first_superuser()

    # Assert
    user_service_mock.get_user_by_username.assert_not_called()
    user_service_mock.create_user.assert_not_called()


@pytest.mark.asyncio
async def test_initialize_first_superuser_when_user_already_exists(
    db_session: AsyncSession,
):
    """Test that superuser creation is skipped when user already exists."""
    # Arrange
    existing_user = User(
        id=1,
        username=settings.FIRST_SUPERUSER_USERNAME,
        email=settings.FIRST_SUPERUSER_EMAIL,
        is_superuser=True,
    )

    user_service_mock = AsyncMock(spec=UserService)
    user_service_mock.get_user_by_username.return_value = existing_user

    # Create service with mocked dependencies
    init_service = InitializationService(db_session)
    init_service.user_service = user_service_mock

    # Ensure settings have required values for this test
    with (
        patch("app.core.config.settings.FIRST_SUPERUSER_USERNAME", "admin"),
        patch("app.core.config.settings.FIRST_SUPERUSER_EMAIL", "admin@example.com"),
        patch("app.core.config.settings.FIRST_SUPERUSER_PASSWORD", "password"),
    ):

        # Act
        await init_service.initialize_first_superuser()

    # Assert
    user_service_mock.get_user_by_username.assert_called_once()
    user_service_mock.create_user.assert_not_called()


@pytest.mark.asyncio
async def test_initialize_first_superuser_success(db_session: AsyncSession):
    """Test successful creation of first superuser."""
    # Arrange
    username = "testadmin"
    email = "testadmin@example.com"
    password = "testpassword"

    user_service_mock = AsyncMock(spec=UserService)
    user_service_mock.get_user_by_username.return_value = None

    new_user = User(id=1, username=username, email=email, is_superuser=True)
    user_service_mock.create_user.return_value = new_user

    db_session_mock = AsyncMock(spec=AsyncSession)

    # Create service with mocked dependencies
    init_service = InitializationService(db_session_mock)
    init_service.user_service = user_service_mock
    init_service.db = db_session_mock

    # Act
    with (
        patch("app.core.config.settings.FIRST_SUPERUSER_USERNAME", username),
        patch("app.core.config.settings.FIRST_SUPERUSER_EMAIL", email),
        patch("app.core.config.settings.FIRST_SUPERUSER_PASSWORD", password),
    ):

        await init_service.initialize_first_superuser()

    # Assert
    user_service_mock.get_user_by_username.assert_called_once_with(username)
    user_service_mock.create_user.assert_called_once()

    # Verify user data passed to create_user
    create_args = user_service_mock.create_user.call_args.args[0]
    assert isinstance(create_args, UserCreate)
    assert create_args.username == username
    assert create_args.email == email
    assert create_args.password == password
    assert create_args.is_superuser is True

    db_session_mock.commit.assert_called_once()


@pytest.mark.asyncio
async def test_create_default_admin_user(db_session: AsyncSession):
    """Test creating default admin user."""
    # Arrange
    user_service_mock = AsyncMock(spec=UserService)

    admin_user = User(
        id=1,
        username="admin",
        email="admin@example.com",
        full_name="System Administrator",
        is_active=True,
        is_superuser=True,
    )
    user_service_mock.create_user.return_value = admin_user

    db_session_mock = AsyncMock(spec=AsyncSession)

    # Create service with mocked dependencies
    init_service = InitializationService(db_session_mock)
    init_service.user_service = user_service_mock
    init_service.db = db_session_mock

    # Patch UserCreate to bypass password validation
    with patch("app.services.initialization_service.UserCreate") as mock_user_create:
        mock_user_create.return_value = UserCreate(
            username="admin",
            email="admin@example.com",
            password="adminpassword123",  # Using a valid password length
            full_name="System Administrator",
            is_active=True,
            is_superuser=True,
        )

        # Act
        result = await init_service._create_default_admin_user()

    # Assert
    assert result is admin_user
    user_service_mock.create_user.assert_called_once()
    db_session_mock.commit.assert_called_once()


@pytest.mark.asyncio
async def test_initialize_with_no_existing_users(db_session: AsyncSession):
    """Test full initialization flow when no users exist in the system."""
    # Arrange
    # Create a real service instance
    init_service = InitializationService(db_session)

    # Set up the mock to return 0 users when execute is called
    user_count_result = MagicMock()
    user_count_result.scalar.return_value = 0
    db_mock = AsyncMock()
    db_mock.execute = AsyncMock(return_value=user_count_result)

    # Act
    # Need to patch select, func, and our methods to avoid actual DB queries and logic
    with (
        patch("app.services.initialization_service.select"),
        patch("app.services.initialization_service.func"),
        patch("app.services.initialization_service.User"),
        patch.object(
            InitializationService,
            "initialize_default_organization",
            new_callable=AsyncMock,
        ) as init_org_mock,
        patch.object(
            InitializationService, "initialize_first_superuser", new_callable=AsyncMock
        ) as init_user_mock,
        patch.object(
            InitializationService, "_create_default_admin_user", new_callable=AsyncMock
        ) as create_admin_mock,
        patch.object(init_service, "db", db_mock),
    ):

        # Call the initialize method on our service
        await init_service.initialize()

    # Assert
    # Verify our mocked methods were called
    init_org_mock.assert_awaited_once()
    init_user_mock.assert_awaited_once()
    create_admin_mock.assert_awaited_once()
    db_mock.execute.assert_called_once()


@pytest.mark.asyncio
async def test_initialize_with_existing_users(db_session: AsyncSession):
    """Test full initialization flow when users already exist in the system."""
    # Arrange
    # Create a real service instance
    init_service = InitializationService(db_session)

    # Mock db.execute to return user count > 0
    mock_result = MagicMock()
    mock_result.scalar.return_value = 3  # 3 users exist

    db_mock = AsyncMock()
    db_mock.execute = AsyncMock(return_value=mock_result)

    # Create a mock organization to return
    mock_org = Organization(id=1)

    # Act
    with (
        patch("app.services.initialization_service.select"),
        patch("app.services.initialization_service.func"),
        patch("app.services.initialization_service.User"),
        patch.object(
            InitializationService,
            "initialize_default_organization",
            new_callable=AsyncMock,
            return_value=mock_org,
        ) as init_org_mock,
        patch.object(
            InitializationService, "initialize_first_superuser", new_callable=AsyncMock
        ) as init_user_mock,
        patch.object(
            InitializationService, "_create_default_admin_user", new_callable=AsyncMock
        ) as create_admin_mock,
        patch.object(init_service, "db", db_mock),
    ):

        await init_service.initialize()

    # Assert
    init_org_mock.assert_awaited_once()
    init_user_mock.assert_awaited_once()
    create_admin_mock.assert_not_awaited()
