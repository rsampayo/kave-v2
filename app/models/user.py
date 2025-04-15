"""Module providing User model functionality."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class User(Base):
    """Model representing a user for authentication and authorization.

    This model stores the details of users who can authenticate to access
    protected endpoints in the application.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        primary_key=True, index=True, comment="Unique identifier for the user"
    )
    username: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, comment="Username for login"
    )
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, comment="Email address of the user"
    )
    full_name: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="Full name of the user"
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255), comment="Hashed password for authentication"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, comment="Whether the user is active"
    )
    is_superuser: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="Whether the user is a superuser"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        comment="Timestamp when the user was created",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="Timestamp when the user was last updated",
    )
