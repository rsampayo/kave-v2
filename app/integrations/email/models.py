"""Module providing Models functionality for the integrations email."""

import logging
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

# Set up logging
logger = logging.getLogger(__name__)


class EmailAttachment(BaseModel):
    """Data model for email attachments."""

    name: str = Field(description="The filename of the attachment")
    type: str = Field(description="The MIME type of the attachment")
    content: str | None = Field(
        None, description="The base64-encoded content of the attachment"
    )
    url: str | None = Field(None, description="The URL to download the attachment")

    def to_dict(self) -> dict[str, Any]:
        """Convert model to dictionary, maintaining compatibility."""
        return self.model_dump()


class InboundEmailData(BaseModel):
    """Data model for inbound email details."""

    message_id: str | None = Field(
        None, description="The unique ID of the email message"
    )
    from_email: str | None = Field(None, description="The sender's email address")
    from_name: str | None = Field(None, description="The sender's name")
    subject: str | None = Field(None, description="The email subject line")
    text: str | None = Field(
        None, description="The plain text version of the email body"
    )
    html: str | None = Field(None, description="The HTML version of the email body")
    to: list[str] = Field(
        default_factory=list, description="List of recipient email addresses"
    )
    cc: list[str] = Field(
        default_factory=list, description="List of CC recipient email addresses"
    )
    bcc: list[str] = Field(
        default_factory=list, description="List of BCC recipient email addresses"
    )
    date: datetime | None = Field(None, description="The date the email was sent")
    reply_to: str | None = Field(None, description="The reply-to email address")
    attachments: list[EmailAttachment] = Field(
        default_factory=list, description="List of email attachments"
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert model to dictionary, maintaining compatibility."""
        result = self.model_dump()
        # Handle any specific conversions if needed
        if self.attachments:
            result["attachments"] = [a.to_dict() for a in self.attachments]
        return result


class MailchimpWebhook(BaseModel):
    """Data model for Mailchimp webhooks."""

    type: str | None = Field(None, description="The type of webhook")
    fired_at: datetime | None = Field(None, description="When the webhook was fired")
    data: dict[str, Any] | InboundEmailData = Field(
        default_factory=lambda: {}, description="The webhook payload data"
    )
    event: str | None = Field(None, description="The webhook event type")
    webhook_id: str | None = Field(None, description="The unique ID of the webhook")
    test_mode: bool | None = Field(None, description="Whether this is a test webhook")

    def to_dict(self) -> dict[str, Any]:
        """Convert model to dictionary, maintaining compatibility."""
        result = self.model_dump()

        # Special handling for data when it's an InboundEmailData object
        if isinstance(self.data, InboundEmailData):
            result["data"] = self.data.to_dict()

        return result
