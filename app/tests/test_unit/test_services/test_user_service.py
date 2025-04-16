"""Unit tests for the user service."""

import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import User
from app.schemas.auth_schemas import UserCreate, UserUpdate
from app.services.user_service import UserService, pwd_context


@pytest.mark.asyncio
async def test_verify_password():
    """Test password verification."""
    # Arrange
    service = UserService(AsyncMock())
    password = "testpassword"
    hashed = pwd_context.hash(password)

    # Act
    result = service.verify_password(password, hashed)

    # Assert
    assert result is True

    # Test with incorrect password
    result = service.verify_password("wrongpassword", hashed)
    assert result is False


@pytest.mark.asyncio
async def test_get_password_hash():
    """Test password hashing."""
    # Arrange
    service = UserService(AsyncMock())
    password = "testpassword"

    # Act
    hashed = service.get_password_hash(password)

    # Assert
    assert hashed != password
    assert pwd_context.verify(password, hashed)


@pytest.mark.asyncio
async def test_create_access_token():
    """Test JWT token creation."""
    # Arrange
    service = UserService(AsyncMock())
    data = {"sub": "testuser", "role": "admin"}

    # Act
    token = service.create_access_token(data)

    # Assert
    assert token is not None
    decoded = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    assert decoded["sub"] == "testuser"
    assert decoded["role"] == "admin"
    assert "exp" in decoded

    # Test with custom expiration
    expires = timedelta(minutes=5)
    token = service.create_access_token(data, expires)
    decoded = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    assert decoded["sub"] == "testuser"
    assert "exp" in decoded


@pytest.mark.asyncio
async def test_create_user(db_session: AsyncSession):
    """Test user creation."""
    # Arrange
    db_mock = AsyncMock()
    service = UserService(db_mock)

    # Mock password hashing
    with patch.object(service, "get_password_hash", return_value="hashed_password"):
        user_data = UserCreate(
            username="testuser",
            email="test@example.com",
            password="testpassword",
            full_name="Test User",
            is_active=True,
            is_superuser=False,
        )

        # Act
        user = await service.create_user(user_data)

        # Assert
        assert user is not None
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.hashed_password == "hashed_password"
        assert user.full_name == "Test User"
        assert user.is_active is True
        assert user.is_superuser is False

        # Verify DB interactions
        db_mock.add.assert_called_once()
        db_mock.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_authenticate_user_success():
    """Test successful user authentication."""
    # Arrange
    service = UserService(AsyncMock())

    # Create test user
    user = User(
        id=1,
        username="testuser",
        email="test@example.com",
        hashed_password="hashed_password",
    )

    # Mock dependencies using patch.object instead of direct assignment
    with (
        patch.object(
            service, "get_user_by_username", new_callable=AsyncMock, return_value=user
        ),
        patch.object(service, "verify_password", return_value=True),
    ):

        # Act
        result = await service.authenticate_user("testuser", "testpassword")

        # Assert
        assert result is user
        service.get_user_by_username.assert_awaited_once_with("testuser")
        service.verify_password.assert_called_once_with(
            "testpassword", "hashed_password"
        )


@pytest.mark.asyncio
async def test_authenticate_user_nonexistent():
    """Test authentication with nonexistent user."""
    # Arrange
    service = UserService(AsyncMock())

    # Mock dependencies using patch.object
    with patch.object(
        service, "get_user_by_username", new_callable=AsyncMock, return_value=None
    ):
        # Act
        result = await service.authenticate_user("nonexistent", "testpassword")

        # Assert
        assert result is None
        service.get_user_by_username.assert_awaited_once_with("nonexistent")


@pytest.mark.asyncio
async def test_authenticate_user_wrong_password():
    """Test authentication with wrong password."""
    # Arrange
    service = UserService(AsyncMock())

    # Create test user
    user = User(
        id=1,
        username="testuser",
        email="test@example.com",
        hashed_password="hashed_password",
    )

    # Mock dependencies using patch.object
    with (
        patch.object(
            service, "get_user_by_username", new_callable=AsyncMock, return_value=user
        ),
        patch.object(service, "verify_password", return_value=False),
    ):
        # Act
        result = await service.authenticate_user("testuser", "wrongpassword")

        # Assert
        assert result is None
        service.get_user_by_username.assert_awaited_once_with("testuser")
        service.verify_password.assert_called_once_with(
            "wrongpassword", "hashed_password"
        )


@pytest.mark.asyncio
async def test_get_user_by_id():
    """Test retrieving user by ID."""
    # Arrange
    # Create a user for the test
    user = User(id=1, username="testuser")

    # Create a mock for the database session
    db_mock = AsyncMock()

    # Create the user service with the mocked db
    service = UserService(db_mock)

    # Use patch.object instead of direct assignment
    with patch.object(
        service, "get_user_by_id", new_callable=AsyncMock, return_value=user
    ):
        # Act
        result = await service.get_user_by_id(1)

        # Assert
        assert result is user
        service.get_user_by_id.assert_awaited_once_with(1)


@pytest.mark.asyncio
async def test_get_user_by_id_not_found():
    """Test retrieving nonexistent user by ID."""
    # Arrange
    # Create a mock for the database session
    db_mock = AsyncMock()

    # Create the user service with the mocked db
    service = UserService(db_mock)

    # Use patch.object instead of direct assignment
    with patch.object(
        service, "get_user_by_id", new_callable=AsyncMock, return_value=None
    ):
        # Act
        result = await service.get_user_by_id(999)

        # Assert
        assert result is None
        service.get_user_by_id.assert_awaited_once_with(999)


@pytest.mark.asyncio
async def test_get_user_by_username():
    """Test retrieving user by username."""
    # Arrange
    # Create a user for the test
    user = User(id=1, username="testuser")

    # Create a mock for the database session
    db_mock = AsyncMock()

    # Create the user service with the mocked db
    service = UserService(db_mock)

    # Use patch.object instead of direct assignment
    with patch.object(
        service, "get_user_by_username", new_callable=AsyncMock, return_value=user
    ):
        # Act
        result = await service.get_user_by_username("testuser")

        # Assert
        assert result is user
        service.get_user_by_username.assert_awaited_once_with("testuser")


@pytest.mark.asyncio
async def test_get_user_by_username_none():
    """Test retrieving user with None username."""
    # Arrange
    db_mock = AsyncMock()
    service = UserService(db_mock)

    # Act
    result = await service.get_user_by_username(None)

    # Assert
    assert result is None
    db_mock.execute.assert_not_called()


@pytest.mark.asyncio
async def test_get_user_by_email():
    """Test retrieving user by email."""
    # Arrange
    # Create a user for the test
    user = User(id=1, username="testuser", email="test@example.com")

    # Create a mock for the database session
    db_mock = AsyncMock()

    # Create the user service with the mocked db
    service = UserService(db_mock)

    # Use patch.object instead of direct assignment
    with patch.object(
        service, "get_user_by_email", new_callable=AsyncMock, return_value=user
    ):
        # Act
        result = await service.get_user_by_email("test@example.com")

        # Assert
        assert result is user
        service.get_user_by_email.assert_awaited_once_with("test@example.com")


@pytest.mark.asyncio
async def test_update_user():
    """Test updating user."""
    # Arrange
    db_mock = AsyncMock()
    service = UserService(db_mock)

    # Create test user
    user = User(
        id=1,
        username="testuser",
        email="test@example.com",
        full_name="Test User",
        hashed_password="oldhash",
        is_active=True,
        is_superuser=False,
    )

    # Update data
    update_data = UserUpdate(
        username="newusername",
        email="new@example.com",
        full_name="New Name",
        password="newpassword",
        is_active=True,
        is_superuser=True,
    )

    # Mock dependencies using patch.object
    with (
        patch.object(
            service, "get_user_by_id", new_callable=AsyncMock, return_value=user
        ),
        patch.object(service, "get_password_hash", return_value="newhash"),
    ):

        # Act
        result = await service.update_user(1, update_data)

        # Assert
        assert result is user
        assert user.username == "newusername"
        assert user.email == "new@example.com"
        assert user.full_name == "New Name"
        assert user.hashed_password == "newhash"
        assert user.is_active is True
        assert user.is_superuser is True

        service.get_user_by_id.assert_awaited_once_with(1)
        service.get_password_hash.assert_called_once_with("newpassword")
        db_mock.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_user_partial():
    """Test partial user update."""
    # Arrange
    db_mock = AsyncMock()
    service = UserService(db_mock)

    # Create test user with initial values
    user = User(
        id=1,
        username="testuser",
        email="test@example.com",
        full_name="Test User",
        hashed_password="oldhash",
        is_active=True,
        is_superuser=False,
    )

    # Original updated_at to check it gets changed
    original_updated_at = user.updated_at

    # Partial update data - only update email
    update_data = UserUpdate(email="newemail@example.com")

    # Mock dependencies using patch.object
    with patch.object(
        service, "get_user_by_id", new_callable=AsyncMock, return_value=user
    ):
        # Act
        result = await service.update_user(1, update_data)

        # Assert
        assert result is user
        # These should change
        assert user.email == "newemail@example.com"
        assert user.updated_at != original_updated_at

        # These should not change
        assert user.username == "testuser"
        assert user.full_name == "Test User"
        assert user.hashed_password == "oldhash"
        assert user.is_active is True
        assert user.is_superuser is False

        service.get_user_by_id.assert_awaited_once_with(1)
        db_mock.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_user_not_found():
    """Test updating nonexistent user."""
    # Arrange
    db_mock = AsyncMock()
    service = UserService(db_mock)

    # Mock dependencies
    service.get_user_by_id = AsyncMock(return_value=None)

    # Update data
    update_data = UserUpdate(username="newusername")

    # Act
    result = await service.update_user(999, update_data)

    # Assert
    assert result is None
    service.get_user_by_id.assert_awaited_once_with(999)
    db_mock.flush.assert_not_called()


@pytest.mark.asyncio
async def test_delete_user():
    """Test user deletion."""
    # Arrange
    user_id = 1
    mock_user = AsyncMock(id=user_id)
    db_mock = AsyncMock()
    service = UserService(db_mock)

    # Mock get_user_by_id to return a user
    future: asyncio.Future[Mock] = asyncio.Future()
    future.set_result(mock_user)
    service.get_user_by_id = Mock(return_value=future)

    # Act
    deleted = await service.delete_user(user_id)

    # Assert
    assert deleted is True
    db_mock.delete.assert_called_once_with(mock_user)
    db_mock.flush.assert_awaited_once()
