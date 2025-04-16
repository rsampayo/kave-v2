"""Authentication schemas for API validation and documentation."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class Token(BaseModel):
    """Schema for authentication token response."""

    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(..., description="Token type (typically 'bearer')")


class TokenData(BaseModel):
    """Schema for token payload data."""

    username: Optional[str] = Field(
        None, description="Username of the authenticated user"
    )
    exp: Optional[datetime] = Field(None, description="Token expiration timestamp")


class UserBase(BaseModel):
    """Base schema for User data."""

    username: str = Field(..., description="Username for login")
    email: EmailStr = Field(..., description="Email address of the user")
    full_name: Optional[str] = Field(None, description="Full name of the user")
    is_active: bool = Field(True, description="Whether the user is active")
    is_superuser: bool = Field(False, description="Whether the user is a superuser")


class UserCreate(UserBase):
    """Schema for creating a new user."""

    password: str = Field(
        ..., description="Password for the user (will be hashed)", min_length=8
    )


class UserUpdate(BaseModel):
    """Schema for updating a user."""

    username: Optional[str] = Field(None, description="Username for login")
    email: Optional[EmailStr] = Field(None, description="Email address of the user")
    full_name: Optional[str] = Field(None, description="Full name of the user")
    password: Optional[str] = Field(None, description="New password (will be hashed)")
    is_active: Optional[bool] = Field(None, description="Whether the user is active")
    is_superuser: Optional[bool] = Field(
        None, description="Whether the user is a superuser"
    )


class UserResponse(UserBase):
    """Schema for user responses (used in API endpoints)."""

    id: int = Field(..., description="Unique identifier of the user")
    created_at: datetime = Field(..., description="When the user was created")
    updated_at: datetime = Field(..., description="When the user was last updated")

    model_config = ConfigDict(from_attributes=True)
