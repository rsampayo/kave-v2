"""API v1 router."""

from fastapi import APIRouter

from app.api.v1.endpoints import attachments, email_webhooks

# Create a v1 router with prefix
api_v1_router = APIRouter(prefix="/v1")

# Include API endpoint routers
api_v1_router.include_router(email_webhooks.router)
api_v1_router.include_router(
    attachments.router, prefix="/attachments", tags=["attachments"]
)
