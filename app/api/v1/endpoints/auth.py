"""Authentication API endpoints."""

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps.auth import get_current_active_user, get_current_superuser
from app.api.v1.deps.database import get_db
from app.core.config import settings
from app.models.user import User
from app.schemas.auth_schemas import Token, UserCreate, UserResponse, UserUpdate
from app.services.user_service import UserService, get_user_service

router = APIRouter()


@router.post(
    "/token",
    response_model=Token,
    summary="Create access token for user",
)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    user_service: UserService = Depends(get_user_service),
    db: AsyncSession = Depends(get_db),
) -> Token:
    """Generate an access token for authentication.

    Args:
        form_data: OAuth2 password request form with username and password
        user_service: User service for authentication
        db: Database session

    Returns:
        Token: Access token data

    Raises:
        HTTPException: If authentication fails
    """
    # Authenticate the user
    user = await user_service.authenticate_user(form_data.username, form_data.password)

    # Check authentication result
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create access token with expiration
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = user_service.create_access_token(
        data={"sub": user.username},
        expires_delta=access_token_expires,
    )

    # Return token response
    return Token(access_token=access_token, token_type="bearer")


@router.post(
    "/users",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user",
    dependencies=[Depends(get_current_superuser)],
)
async def create_user(
    user_data: UserCreate,
    user_service: UserService = Depends(get_user_service),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Create a new user (admin only).

    Args:
        user_data: User creation data with username, email, and password
        user_service: User service for user creation
        db: Database session

    Returns:
        UserResponse: Created user data

    Raises:
        HTTPException: If a user with the same username or email already exists
    """
    # Check if user with same username exists
    existing_user = await user_service.get_user_by_username(user_data.username)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User with username {user_data.username!r} already exists",
        )

    # Check if user with same email exists
    existing_user = await user_service.get_user_by_email(user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User with email {user_data.email!r} already exists",
        )

    # Create the user
    user = await user_service.create_user(user_data)
    await db.commit()

    # Return response model
    return UserResponse.model_validate(user)


@router.get(
    "/users/me",
    response_model=UserResponse,
    summary="Get current user information",
)
async def read_users_me(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> UserResponse:
    """Get the current authenticated user's information.

    Args:
        current_user: Current authenticated user

    Returns:
        UserResponse: User information
    """
    return UserResponse.model_validate(current_user)


@router.put(
    "/users/me",
    response_model=UserResponse,
    summary="Update current user information",
)
async def update_user_me(
    user_data: UserUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    user_service: UserService = Depends(get_user_service),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Update the current authenticated user's information.

    Args:
        user_data: User update data
        current_user: Current authenticated user
        user_service: User service for user updates
        db: Database session

    Returns:
        UserResponse: Updated user information

    Raises:
        HTTPException: If update fails
    """
    # If username is changing, check if it's already taken
    if user_data.username and user_data.username != current_user.username:
        existing_user = await user_service.get_user_by_username(user_data.username)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Username {user_data.username!r} already exists",
            )

    # If email is changing, check if it's already taken
    if user_data.email and user_data.email != current_user.email:
        existing_user = await user_service.get_user_by_email(user_data.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Email {user_data.email!r} already exists",
            )

    # Update the user
    updated_user = await user_service.update_user(current_user.id, user_data)
    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    await db.commit()

    # Return response model
    return UserResponse.model_validate(updated_user)
