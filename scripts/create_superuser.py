#!/usr/bin/env python3
"""
Create a superuser in the database.

This script creates a superuser account for the application.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add the project root to the Python path
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

# Third party imports
from passlib.context import CryptContext  # noqa: E402
from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

# Local application imports
from app.db.session import get_db  # noqa: E402
from app.models.user import User  # noqa: E402

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def create_superuser(
    username: str, email: str, password: str, full_name: str = "System Administrator"
) -> None:
    """Create a superuser in the database."""
    # Get a database session
    db_gen = get_db()
    db: AsyncSession = await db_gen.__anext__()

    try:
        # Check if user already exists
        result = await db.execute(select(User).where(User.username == username))
        existing_user = result.scalars().first()

        if existing_user:
            print(f"User '{username}' already exists.")
            return

        # Hash the password
        hashed_password = pwd_context.hash(password)

        # Create the user
        user = User(
            username=username,
            email=email,
            full_name=full_name,
            hashed_password=hashed_password,
            is_active=True,
            is_superuser=True,
        )

        db.add(user)
        await db.commit()
        await db.refresh(user)

        print(f"Superuser '{username}' created successfully with ID {user.id}.")

    except Exception as e:
        await db.rollback()
        print(f"Error creating superuser: {e}")
    finally:
        # Close the session
        try:
            await db_gen.aclose()
        except Exception:
            pass


async def main() -> None:
    """Run the superuser creation."""
    # Default values
    username = os.environ.get("FIRST_SUPERUSER_USERNAME", "admin")
    email = os.environ.get("FIRST_SUPERUSER_EMAIL", "admin@example.com")
    password = os.environ.get("FIRST_SUPERUSER_PASSWORD", "SuperSecurePassword123!")
    full_name = "System Administrator"

    # Create the superuser
    await create_superuser(username, email, password, full_name)


if __name__ == "__main__":
    asyncio.run(main())
