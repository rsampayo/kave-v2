"""Email webhook endpoints module.

This is the main entry point for webhook requests related to email services.
It imports and includes routers from specialized webhook processors
for different providers.

Currently supported webhook providers:
- Mandrill: For handling inbound emails and notifications from Mandrill
"""

import logging

from fastapi import APIRouter

from app.api.endpoints.webhooks.mandrill.router import router as mandrill_router

# Set up logging
logger = logging.getLogger(__name__)

# Create the main webhook router
router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# Include the Mandrill router
router.include_router(
    mandrill_router,
    prefix="/mandrill",
)

# Add routes for additional webhook providers here as they are implemented
# Examples:
# router.include_router(sendgrid_router, prefix="/sendgrid")
# router.include_router(twilio_router, prefix="/twilio")
