"""API dependency injection functions."""

from fastapi import Depends, Request

from app.integrations.email.client import WebhookClient, webhook_client

# Create dependency instance at module level
webhook_client_dependency = Depends(lambda: webhook_client)
