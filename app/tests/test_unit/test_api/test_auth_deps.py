"""Unit tests for authentication dependencies."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from jose import jwt

from app.api.v1.deps.auth import (
    get_current_active_user,
    get_current_superuser,
    get_current_user,
    get_optional_user,
)
from app.core.config import settings
from app.models.user import User
from app.services.user_service import UserService


@pytest.mark.asyncio
async def test_get_current_user_success():
    """Test successful user retrieval."""
    # Arrange
    mock_user = User(id=1, username="testuser", is_active=True)
    mock_db = AsyncMock()
    mock_user_service = AsyncMock(spec=UserService)
    mock_user_service.get_user_by_username.return_value = mock_user

    # Create a valid token
    token_data = {"sub": "testuser"}
    token = jwt.encode(token_data, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    # Act
    user = await get_current_user(mock_db, token, mock_user_service)

    # Assert
    assert user is mock_user
    mock_user_service.get_user_by_username.assert_awaited_once_with("testuser")


@pytest.mark.asyncio
async def test_get_current_user_invalid_token():
    """Test user retrieval with invalid token."""
    # Arrange
    mock_db = AsyncMock()
    mock_user_service = AsyncMock(spec=UserService)

    # Create an invalid token
    token = "invalid-token"

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(mock_db, token, mock_user_service)

    assert exc_info.value.status_code == 401
    assert "Could not validate credentials" in exc_info.value.detail
    mock_user_service.get_user_by_username.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_current_user_missing_username():
    """Test user retrieval with token missing subject."""
    # Arrange
    mock_db = AsyncMock()
    mock_user_service = AsyncMock(spec=UserService)

    # Create a token without a subject
    token_data = {"role": "user"}
    token = jwt.encode(token_data, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(mock_db, token, mock_user_service)

    assert exc_info.value.status_code == 401
    assert "Could not validate credentials" in exc_info.value.detail
    mock_user_service.get_user_by_username.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_current_user_user_not_found():
    """Test user retrieval when user not found in database."""
    # Arrange
    mock_db = AsyncMock()
    mock_user_service = AsyncMock(spec=UserService)
    mock_user_service.get_user_by_username.return_value = None

    # Create a valid token
    token_data = {"sub": "testuser"}
    token = jwt.encode(token_data, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(mock_db, token, mock_user_service)

    assert exc_info.value.status_code == 401
    assert "Could not validate credentials" in exc_info.value.detail
    mock_user_service.get_user_by_username.assert_awaited_once_with("testuser")


@pytest.mark.asyncio
async def test_get_current_user_no_token():
    """Test user retrieval with no token."""
    # Arrange
    mock_db = AsyncMock()
    mock_user_service = AsyncMock(spec=UserService)

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(mock_db, None, mock_user_service)

    assert exc_info.value.status_code == 401
    assert "Not authenticated" in exc_info.value.detail
    mock_user_service.get_user_by_username.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_optional_user_with_token():
    """Test optional user retrieval with valid token."""
    # Arrange
    mock_user = User(id=1, username="testuser", is_active=True)
    mock_db = AsyncMock()
    mock_user_service = AsyncMock(spec=UserService)

    # Mock get_current_user
    with patch("app.api.v1.deps.auth.get_current_user", return_value=mock_user):
        # Create a valid token
        token_data = {"sub": "testuser"}
        token = jwt.encode(
            token_data, settings.SECRET_KEY, algorithm=settings.ALGORITHM
        )

        # Act
        user = await get_optional_user(mock_db, token, mock_user_service)

        # Assert
        assert user is mock_user


@pytest.mark.asyncio
async def test_get_optional_user_no_token():
    """Test optional user retrieval with no token."""
    # Arrange
    mock_db = AsyncMock()
    mock_user_service = AsyncMock(spec=UserService)

    # Act
    user = await get_optional_user(mock_db, None, mock_user_service)

    # Assert
    assert user is None


@pytest.mark.asyncio
async def test_get_optional_user_invalid_token():
    """Test optional user retrieval with invalid token."""
    # Arrange
    mock_db = AsyncMock()
    mock_user_service = AsyncMock(spec=UserService)

    # Mock get_current_user to raise exception
    with patch(
        "app.api.v1.deps.auth.get_current_user",
        side_effect=HTTPException(status_code=401, detail="Invalid"),
    ):
        # Act
        user = await get_optional_user(mock_db, "invalid-token", mock_user_service)

        # Assert
        assert user is None


@pytest.mark.asyncio
async def test_get_current_active_user_active():
    """Test retrieval of active user."""
    # Arrange
    mock_user = User(id=1, username="testuser", is_active=True)

    # Act
    user = await get_current_active_user(mock_user)

    # Assert
    assert user is mock_user


@pytest.mark.asyncio
async def test_get_current_active_user_inactive():
    """Test retrieval of inactive user."""
    # Arrange
    mock_user = User(id=1, username="testuser", is_active=False)

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await get_current_active_user(mock_user)

    assert exc_info.value.status_code == 403
    assert "Inactive user" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_current_superuser_is_superuser():
    """Test retrieval of superuser."""
    # Arrange
    mock_user = User(id=1, username="admin", is_active=True, is_superuser=True)

    # Act
    user = await get_current_superuser(mock_user)

    # Assert
    assert user is mock_user


@pytest.mark.asyncio
async def test_get_current_superuser_not_superuser():
    """Test retrieval of non-superuser."""
    # Arrange
    mock_user = User(id=1, username="user", is_active=True, is_superuser=False)

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await get_current_superuser(mock_user)

    assert exc_info.value.status_code == 403
    assert "doesn't have enough privileges" in exc_info.value.detail
