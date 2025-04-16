"""Module providing User Service functionality."""

import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends
from jose import jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps.database import get_db
from app.core.config import settings
from app.models.user import User
from app.schemas.auth_schemas import UserCreate, UserUpdate

logger = logging.getLogger(__name__)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class UserService:
    """Service for managing users."""

    def __init__(self, db: AsyncSession):
        """Initialize the user service.

        Args:
            db: Database session
        """
        self.db = db
        self.pwd_context = pwd_context

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against a hash.

        Args:
            plain_password: Plain text password
            hashed_password: Hashed password

        Returns:
            bool: True if password matches, False otherwise
        """
        return bool(self.pwd_context.verify(plain_password, hashed_password))

    def get_password_hash(self, password: str) -> str:
        """Hash a password.

        Args:
            password: Plain text password

        Returns:
            str: Hashed password
        """
        return str(self.pwd_context.hash(password))

    def create_access_token(
        self, data: dict, expires_delta: Optional[timedelta] = None
    ) -> str:
        """Create a new JWT token.

        Args:
            data: Data to encode in the token
            expires_delta: Optional expiration delta

        Returns:
            str: JWT token
        """
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(
                minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
            )
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(
            to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
        )
        return str(encoded_jwt)

    async def create_user(self, data: UserCreate) -> User:
        """Create a new user.

        Args:
            data: User data

        Returns:
            User: The created user
        """
        # Hash the password
        hashed_password = self.get_password_hash(data.password)

        # Create the user model
        user = User(
            username=data.username,
            email=data.email,
            full_name=data.full_name,
            hashed_password=hashed_password,
            is_active=data.is_active,
            is_superuser=data.is_superuser,
        )

        # Add to database
        self.db.add(user)
        await self.db.flush()

        return user

    async def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """Authenticate a user.

        Args:
            username: Username
            password: Plain text password

        Returns:
            Optional[User]: The user if authenticated, None otherwise
        """
        user = await self.get_user_by_username(username)

        if not user:
            return None

        if not self.verify_password(password, user.hashed_password):
            return None

        return user

    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Get a user by ID.

        Args:
            user_id: User ID

        Returns:
            Optional[User]: The user if found, None otherwise
        """
        query = select(User).where(User.id == user_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_user_by_username(self, username: Optional[str]) -> Optional[User]:
        """Get a user by username.

        Args:
            username: Username

        Returns:
            Optional[User]: The user if found, None otherwise
        """
        if username is None:
            return None

        query = select(User).where(User.username == username)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get a user by email.

        Args:
            email: Email address

        Returns:
            Optional[User]: The user if found, None otherwise
        """
        query = select(User).where(User.email == email)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def update_user(self, user_id: int, data: UserUpdate) -> Optional[User]:
        """Update a user.

        Args:
            user_id: User ID
            data: Updated user data

        Returns:
            Optional[User]: The updated user if found, None otherwise
        """
        # Get the user
        user = await self.get_user_by_id(user_id)
        if not user:
            return None

        # Update fields if provided
        if data.username is not None:
            user.username = data.username
        if data.email is not None:
            user.email = data.email
        if data.full_name is not None:
            user.full_name = data.full_name
        if data.password is not None:
            user.hashed_password = self.get_password_hash(data.password)
        if data.is_active is not None:
            user.is_active = data.is_active
        if data.is_superuser is not None:
            user.is_superuser = data.is_superuser

        # Update the timestamp
        user.updated_at = datetime.utcnow()

        # Save changes
        await self.db.flush()

        return user

    async def delete_user(self, user_id: int) -> bool:
        """Delete a user by ID.

        Args:
            user_id: User ID

        Returns:
            bool: True if the user was deleted, False otherwise
        """
        user = await self.get_user_by_id(user_id)
        if not user:
            return False

        await self.db.delete(user)
        await self.db.flush()

        return True


async def get_user_service(db: AsyncSession = Depends(get_db)) -> UserService:
    """Dependency function to get the user service.

    Args:
        db: Database session

    Returns:
        UserService: The user service
    """
    return UserService(db=db)
