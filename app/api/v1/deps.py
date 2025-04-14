"""API dependency injection functions."""

from fastapi import Depends

from app.api.v1.deps.database import get_db
from app.api.v1.deps.email import get_email_service, get_webhook_client
from app.api.v1.deps.storage import get_storage_service
from app.integrations.email.client import webhook_client

# Create dependency instance at module level
webhook_client_dependency = Depends(lambda: webhook_client)

__all__ = [
    "get_db",
    "get_storage_service",
    "get_email_service",
    "get_webhook_client",
    "webhook_client_dependency",
]
