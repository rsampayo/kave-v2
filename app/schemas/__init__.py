"""Pydantic schemas for request/response validation."""

from app.schemas.webhook_schemas import InboundEmailData, MailchimpWebhook

__all__ = ["MailchimpWebhook", "InboundEmailData"]
