"""API v1 router."""

from fastapi import APIRouter

from app.api.v1.endpoints import attachments, auth, email_webhooks, organizations
# Will add redis_demo support later when file is moved
# from app.api.v1.endpoints import redis_demo

# Create a v1 router with prefix
api_v1_router = APIRouter(prefix="/v1")

# Include API endpoint routers
api_v1_router.include_router(email_webhooks.router)
api_v1_router.include_router(
    attachments.router, prefix="/attachments", tags=["attachments"]
)
api_v1_router.include_router(
    organizations.router, prefix="/organizations", tags=["organizations"]
)
api_v1_router.include_router(auth.router, prefix="/auth", tags=["auth"])

# Include Redis demo endpoints (for testing Redis integration)
# api_v1_router.include_router(redis_demo.router, prefix="/redis-demo")
