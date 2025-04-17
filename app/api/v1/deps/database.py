"""Database dependencies for dependency injection."""

from typing import TypeVar

from app.db.session import get_db

T = TypeVar("T")

__all__ = ["get_db"]

# The get_db dependency is now imported directly from app.db.session
# This eliminated duplication while maintaining backward compatibility
