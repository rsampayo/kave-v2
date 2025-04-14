"""API dependency injection modules."""

from app.api.v1.deps.auth import (
    get_current_active_user,
    get_current_user,
    get_optional_user,
)
from app.api.v1.deps.database import get_db
from app.api.v1.deps.email import (
    get_attachment_service,
    get_email_service,
    get_webhook_client,
)
from app.api.v1.deps.storage import get_storage_service

__all__ = [
    "get_db",
    "get_storage_service",
    "get_webhook_client",
    "get_email_service",
    "get_attachment_service",
    "get_current_user",
    "get_optional_user",
    "get_current_active_user",
]
