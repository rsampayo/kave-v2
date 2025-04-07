from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class EmailAttachment(BaseModel):
    """Data model for email attachments."""

    name: str = Field(description="The filename of the attachment")
    type: str = Field(description="The MIME type of the attachment")
    content: Optional[str] = Field(
        None, description="The base64-encoded content of the attachment"
    )
    url: Optional[str] = Field(None, description="The URL to download the attachment")

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary, maintaining compatibility."""
        return self.model_dump()


class InboundEmailData(BaseModel):
    """Data model for inbound email details."""

    message_id: Optional[str] = Field(
        None, description="The unique ID of the email message"
    )
    from_email: Optional[str] = Field(None, description="The sender's email address")
    from_name: Optional[str] = Field(None, description="The sender's name")
    subject: Optional[str] = Field(None, description="The email subject line")
    text: Optional[str] = Field(
        None, description="The plain text version of the email body"
    )
    html: Optional[str] = Field(None, description="The HTML version of the email body")
    to: List[str] = Field(
        default_factory=list, description="List of recipient email addresses"
    )
    cc: List[str] = Field(
        default_factory=list, description="List of CC recipient email addresses"
    )
    bcc: List[str] = Field(
        default_factory=list, description="List of BCC recipient email addresses"
    )
    date: Optional[datetime] = Field(None, description="The date the email was sent")
    reply_to: Optional[str] = Field(None, description="The reply-to email address")
    attachments: List[EmailAttachment] = Field(
        default_factory=list, description="List of email attachments"
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary, maintaining compatibility."""
        result = self.model_dump()
        # Handle any specific conversions if needed
        if self.attachments:
            result["attachments"] = [a.to_dict() for a in self.attachments]
        return result


class MailchimpWebhook(BaseModel):
    """Data model for Mailchimp webhooks."""

    type: Optional[str] = Field(None, description="The type of webhook")
    fired_at: Optional[datetime] = Field(None, description="When the webhook was fired")
    data: Union[Dict[str, Any], InboundEmailData] = Field(
        default_factory=lambda: {}, description="The webhook payload data"
    )
    event: Optional[str] = Field(None, description="The webhook event type")
    webhook_id: Optional[str] = Field(None, description="The unique ID of the webhook")
    test_mode: Optional[bool] = Field(
        None, description="Whether this is a test webhook"
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary, maintaining compatibility."""
        result = self.model_dump()

        # Special handling for data when it's an InboundEmailData object
        if isinstance(self.data, InboundEmailData):
            result["data"] = self.data.to_dict()

        return result
