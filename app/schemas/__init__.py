"""Schema definitions for API request and response models."""

from app.schemas.auth_schemas import (
    Token,
    TokenData,
    UserCreate,
    UserResponse,
    UserUpdate,
)
from app.schemas.organization_schemas import (
    OrganizationCreate,
    OrganizationResponse,
    OrganizationUpdate,
)
from app.schemas.webhook_schemas import (
    EmailAttachment,
    InboundEmailData,
    MailchimpWebhook,
    WebhookResponse,
)

__all__ = [
    "EmailAttachment",
    "InboundEmailData",
    "MailchimpWebhook",
    "WebhookResponse",
    "OrganizationCreate",
    "OrganizationResponse",
    "OrganizationUpdate",
    "Token",
    "TokenData",
    "UserCreate",
    "UserResponse",
    "UserUpdate",
]
