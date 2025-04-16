"""Unit tests for authentication endpoints."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException, status

from app.api.v1.endpoints.auth import (
    create_user,
    login_for_access_token,
    read_users_me,
    update_user_me,
)
from app.core.config import settings
from app.models.user import User
from app.schemas.auth_schemas import Token, UserCreate, UserUpdate


@pytest.mark.asyncio
async def test_login_for_access_token_success():
    """Test successful login and token generation."""
    # Arrange
    # Create a properly mocked user
    mock_user = User(
        id=1,
        username="testuser",
        email="test@example.com",
        is_active=True,
        is_superuser=False,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        hashed_password="hashed_password",
    )

    mock_db = AsyncMock()
    mock_user_service = AsyncMock()
    mock_user_service.authenticate_user.return_value = mock_user
    # Make create_access_token return a regular string, not a coroutine
    mock_user_service.create_access_token = MagicMock(return_value="test_token")

    # Mock form data
    form_data = MagicMock()
    form_data.username = "testuser"
    form_data.password = "password123"

    # Act
    result = await login_for_access_token(form_data, mock_user_service, mock_db)

    # Assert
    assert isinstance(result, Token)
    assert result.access_token == "test_token"
    assert result.token_type == "bearer"
    mock_user_service.authenticate_user.assert_awaited_once_with(
        "testuser", "password123"
    )
    mock_user_service.create_access_token.assert_called_once()
    # Verify token expiration time is used
    called_kwargs = mock_user_service.create_access_token.call_args.kwargs
    assert isinstance(called_kwargs["expires_delta"], timedelta)
    assert (
        called_kwargs["expires_delta"].total_seconds()
        == settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@pytest.mark.asyncio
async def test_login_for_access_token_invalid_credentials():
    """Test login with invalid credentials."""
    # Arrange
    mock_db = AsyncMock()
    mock_user_service = AsyncMock()
    mock_user_service.authenticate_user.return_value = None

    # Mock form data
    form_data = MagicMock()
    form_data.username = "testuser"
    form_data.password = "wrong_password"

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await login_for_access_token(form_data, mock_user_service, mock_db)

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Incorrect username or password" in exc_info.value.detail
    # Add type assertion to ensure headers is a dict
    headers = exc_info.value.headers
    assert isinstance(headers, dict)
    assert headers["WWW-Authenticate"] == "Bearer"
    mock_user_service.authenticate_user.assert_awaited_once_with(
        "testuser", "wrong_password"
    )
    mock_user_service.create_access_token.assert_not_called()


@pytest.mark.asyncio
async def test_create_user_success():
    """Test successful user creation."""
    # Arrange
    # Create a properly mocked user
    mock_user = User(
        id=1,
        username="newuser",
        email="new@example.com",
        full_name="New User",
        is_active=True,
        is_superuser=False,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        hashed_password="hashed_password",
    )

    mock_db = AsyncMock()
    mock_user_service = AsyncMock()
    mock_user_service.get_user_by_username.return_value = None
    mock_user_service.get_user_by_email.return_value = None
    mock_user_service.create_user.return_value = mock_user

    # Create user data
    user_data = UserCreate(
        username="newuser",
        email="new@example.com",
        password="Password123!",
        full_name="New User",
    )

    # Act
    result = await create_user(user_data, mock_user_service, mock_db)

    # Assert
    assert result.username == "newuser"
    assert result.email == "new@example.com"
    assert result.full_name == "New User"
    assert result.is_active is True
    assert "password" not in result.model_dump()
    mock_user_service.get_user_by_username.assert_awaited_once_with("newuser")
    mock_user_service.get_user_by_email.assert_awaited_once_with("new@example.com")
    mock_user_service.create_user.assert_awaited_once_with(user_data)
    mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_user_duplicate_username():
    """Test creating a user with a username that already exists."""
    # Arrange
    existing_user = User(
        id=1,
        username="existinguser",
        email="existing@example.com",
        is_active=True,
        is_superuser=False,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        hashed_password="hashed_password",
    )

    mock_db = AsyncMock()
    mock_user_service = AsyncMock()
    mock_user_service.get_user_by_username.return_value = existing_user

    # Create user data with duplicate username
    user_data = UserCreate(
        username="existinguser",
        email="new@example.com",
        password="Password123!",
    )

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await create_user(user_data, mock_user_service, mock_db)

    assert exc_info.value.status_code == status.HTTP_409_CONFLICT
    assert "already exists" in exc_info.value.detail
    mock_user_service.get_user_by_username.assert_awaited_once_with("existinguser")
    mock_user_service.get_user_by_email.assert_not_awaited()
    mock_user_service.create_user.assert_not_awaited()
    mock_db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_user_duplicate_email():
    """Test creating a user with an email that already exists."""
    # Arrange
    existing_user = User(
        id=1,
        username="existinguser",
        email="existing@example.com",
        is_active=True,
        is_superuser=False,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        hashed_password="hashed_password",
    )

    mock_db = AsyncMock()
    mock_user_service = AsyncMock()
    mock_user_service.get_user_by_username.return_value = None
    mock_user_service.get_user_by_email.return_value = existing_user

    # Create user data with duplicate email
    user_data = UserCreate(
        username="newuser",
        email="existing@example.com",
        password="Password123!",
    )

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await create_user(user_data, mock_user_service, mock_db)

    assert exc_info.value.status_code == status.HTTP_409_CONFLICT
    assert "already exists" in exc_info.value.detail
    mock_user_service.get_user_by_username.assert_awaited_once_with("newuser")
    mock_user_service.get_user_by_email.assert_awaited_once_with("existing@example.com")
    mock_user_service.create_user.assert_not_awaited()
    mock_db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_read_users_me():
    """Test reading current user information."""
    # Arrange
    mock_user = User(
        id=1,
        username="testuser",
        email="test@example.com",
        full_name="Test User",
        is_active=True,
        is_superuser=False,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        hashed_password="hashed_password",
    )

    # Act
    result = await read_users_me(mock_user)

    # Assert
    assert result.id == 1
    assert result.username == "testuser"
    assert result.email == "test@example.com"
    assert result.full_name == "Test User"
    assert result.is_active is True
    assert "password" not in result.model_dump()


@pytest.mark.asyncio
async def test_update_user_me_success():
    """Test successful user update."""
    # Arrange
    mock_user = User(
        id=1,
        username="testuser",
        email="test@example.com",
        full_name="Test User",
        is_active=True,
        is_superuser=False,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        hashed_password="hashed_password",
    )

    updated_user = User(
        id=1,
        username="testuser",
        email="test@example.com",
        full_name="Updated Name",
        is_active=True,
        is_superuser=False,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        hashed_password="hashed_password",
    )

    mock_db = AsyncMock()
    mock_user_service = AsyncMock()
    mock_user_service.update_user.return_value = updated_user

    # Create update data
    update_data = UserUpdate(full_name="Updated Name")

    # Act
    result = await update_user_me(update_data, mock_user, mock_user_service, mock_db)

    # Assert
    assert result.id == 1
    assert result.username == "testuser"
    assert result.email == "test@example.com"
    assert result.full_name == "Updated Name"
    assert result.is_active is True
    mock_user_service.update_user.assert_awaited_once_with(1, update_data)
    mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_user_me_duplicate_username():
    """Test updating user with a username that already exists."""
    # Arrange
    mock_user = User(
        id=1,
        username="testuser",
        email="test@example.com",
        is_active=True,
        is_superuser=False,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        hashed_password="hashed_password",
    )

    existing_user = User(
        id=2,
        username="existinguser",
        email="existing@example.com",
        is_active=True,
        is_superuser=False,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        hashed_password="hashed_password",
    )

    mock_db = AsyncMock()
    mock_user_service = AsyncMock()
    mock_user_service.get_user_by_username.return_value = existing_user

    # Create update data with duplicate username
    update_data = UserUpdate(username="existinguser")

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await update_user_me(update_data, mock_user, mock_user_service, mock_db)

    assert exc_info.value.status_code == status.HTTP_409_CONFLICT
    assert "already exists" in exc_info.value.detail
    mock_user_service.get_user_by_username.assert_awaited_once_with("existinguser")
    mock_user_service.update_user.assert_not_awaited()
    mock_db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_user_me_duplicate_email():
    """Test updating user with an email that already exists."""
    # Arrange
    mock_user = User(
        id=1,
        username="testuser",
        email="test@example.com",
        is_active=True,
        is_superuser=False,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        hashed_password="hashed_password",
    )

    existing_user = User(
        id=2,
        username="otheruser",
        email="existing@example.com",
        is_active=True,
        is_superuser=False,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        hashed_password="hashed_password",
    )

    mock_db = AsyncMock()
    mock_user_service = AsyncMock()
    mock_user_service.get_user_by_username.return_value = None
    mock_user_service.get_user_by_email.return_value = existing_user

    # Create update data with duplicate email
    update_data = UserUpdate(email="existing@example.com")

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await update_user_me(update_data, mock_user, mock_user_service, mock_db)

    assert exc_info.value.status_code == status.HTTP_409_CONFLICT
    assert "already exists" in exc_info.value.detail
    mock_user_service.get_user_by_email.assert_awaited_once_with("existing@example.com")
    mock_user_service.update_user.assert_not_awaited()
    mock_db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_user_me_user_not_found():
    """Test updating a user that doesn't exist."""
    # Arrange
    mock_user = User(
        id=1,
        username="testuser",
        email="test@example.com",
        is_active=True,
        is_superuser=False,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        hashed_password="hashed_password",
    )

    mock_db = AsyncMock()
    mock_user_service = AsyncMock()
    mock_user_service.get_user_by_username.return_value = None
    mock_user_service.get_user_by_email.return_value = None
    mock_user_service.update_user.return_value = None

    # Create update data
    update_data = UserUpdate(full_name="Updated Name")

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await update_user_me(update_data, mock_user, mock_user_service, mock_db)

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
    assert "User not found" in exc_info.value.detail
    mock_user_service.update_user.assert_awaited_once_with(1, update_data)
    mock_db.commit.assert_not_awaited()
