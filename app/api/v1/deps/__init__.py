"""API dependency injection functions module."""

from app.api.v1.deps.auth import (
    get_current_active_user,
    get_current_superuser,
    get_current_user,
)
from app.api.v1.deps.database import get_db
from app.api.v1.deps.email import get_email_service, get_webhook_client
from app.api.v1.deps.storage import get_storage_service

__all__ = [
    "get_db",
    "get_storage_service",
    "get_email_service",
    "get_webhook_client",
    "get_current_user",
    "get_current_active_user",
    "get_current_superuser",
]
