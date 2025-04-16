"""Authentication and authorization dependencies for dependency injection."""

from typing import Annotated, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps.database import get_db
from app.core.config import settings
from app.models.user import User
from app.schemas.auth_schemas import TokenData
from app.services.user_service import UserService, get_user_service

__all__ = ["get_current_user", "get_optional_user", "get_current_active_user"]


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/v1/auth/token", auto_error=True)


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    token: Optional[str] = Depends(oauth2_scheme),
    user_service: UserService = Depends(get_user_service),
) -> User:
    """Get the current authenticated user.

    Args:
        db: Database session
        token: JWT token from OAuth2 scheme
        user_service: User service

    Returns:
        User: The authenticated user

    Raises:
        HTTPException: If authentication fails
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        # Decode the JWT token
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )

        # Extract username from token
        username: Optional[str] = payload.get("sub")
        if username is None:
            raise credentials_exception

        # Create token data object
        token_data = TokenData(username=username, exp=payload.get("exp"))
    except JWTError:
        raise credentials_exception

    # Get the user from the database
    # username is guaranteed to be a string by this point
    user = await user_service.get_user_by_username(token_data.username)
    if user is None:
        raise credentials_exception

    return user


async def get_optional_user(
    db: AsyncSession = Depends(get_db),
    token: Optional[str] = Depends(oauth2_scheme),
    user_service: UserService = Depends(get_user_service),
) -> Optional[User]:
    """Get the current user if authenticated, None otherwise.

    Args:
        db: Database session
        token: Optional JWT token from OAuth2 scheme
        user_service: User service

    Returns:
        Optional[User]: User information or None if not authenticated
    """
    if not token:
        return None

    try:
        # Try to get the current user
        return await get_current_user(db, token, user_service)
    except HTTPException:
        return None


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Get the current active user.

    Args:
        current_user: Current authenticated user

    Returns:
        User: Active user information

    Raises:
        HTTPException: If the user is inactive
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user"
        )
    return current_user


async def get_current_superuser(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> User:
    """Get the current superuser.

    Args:
        current_user: Current active user

    Returns:
        User: Superuser information

    Raises:
        HTTPException: If the user is not a superuser
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user doesn't have enough privileges",
        )
    return current_user
