"""Module providing Webhook Schemas functionality for the schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class EmailAttachment(BaseModel):
    """Schema for email attachment data in a webhook."""

    name: str = Field(..., description="The filename of the attachment")
    type: str = Field(..., description="MIME type of the attachment")
    content: str | None = Field(
        None, description="Content of the attachment (base64-encoded if base64=True)"
    )
    content_id: str | None = Field(
        None, description="Content ID for inline attachments"
    )
    size: int | None = Field(None, description="Size of the attachment in bytes")
    base64: bool | None = Field(
        True, description="Whether content is base64 encoded (default: True)"
    )


class InboundEmailData(BaseModel):
    """Schema representing the parsed email data from a webhook."""

    message_id: str = Field(
        ...,
        description="Unique identifier for the email",
    )
    from_email: EmailStr = Field(..., description="Email address of the sender")
    from_name: str | None = Field(None, description="Display name of the sender")
    to_email: EmailStr = Field(..., description="Email address of the recipient")
    subject: str = Field(..., description="Email subject line")
    body_plain: str | None = Field(None, description="Plain text body of the email")
    body_html: str | None = Field(None, description="HTML body of the email")
    headers: dict[str, str] = Field(default_factory=dict, description="Email headers")
    attachments: list[EmailAttachment] = Field(
        default_factory=list, description="List of email attachments"
    )


class WebhookData(BaseModel):
    """Schema for incoming email webhook payload."""

    webhook_id: str = Field(..., description="Unique identifier for the webhook event")
    event: str = Field(..., description="Type of event that triggered the webhook")
    timestamp: datetime = Field(..., description="When the event occurred")

    # Email-specific fields for different event types
    data: InboundEmailData = Field(
        ...,
        description="The email data payload",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "webhook_id": "wh_123456789",
                "event": "inbound_email",
                "timestamp": "2023-04-01T12:00:00Z",
                "data": {
                    "message_id": "<example123@mail.example.com>",
                    "from_email": "sender@example.com",
                    "from_name": "John Doe",
                    "to_email": "recipient@kave.com",
                    "subject": "Test Email",
                    "body_plain": "This is a test email",
                    "body_html": (
                        "<html><body><p>This is a test email</p></body></html>"
                    ),
                    "headers": {
                        "Return-Path": "<sender@example.com>",
                        "MIME-Version": "1.0",
                    },
                    "attachments": [
                        {
                            "name": "document.pdf",
                            "type": "application/pdf",
                            "size": 12345,
                            "content_id": "attach1",
                        }
                    ],
                },
            }
        }
    )


# Backwards compatibility alias
MailchimpWebhook = WebhookData


class WebhookResponse(BaseModel):
    """Schema for webhook API responses."""

    status: str = Field(..., description="Status of the operation (success or error)")
    message: str = Field(..., description="Human-readable result message")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"status": "success", "message": "Email processed successfully"}
        }
    )


class DetailedWebhookResponse(WebhookResponse):
    """Schema for detailed webhook API responses with additional data."""

    data: dict | None = Field(None, description="Additional response data")
    processed_at: datetime = Field(
        default_factory=datetime.utcnow, description="When the webhook was processed"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "success",
                "message": "Email processed successfully",
                "data": {
                    "email_id": 123,
                    "message_id": "<example123@mail.example.com>",
                    "attachments_count": 1,
                },
                "processed_at": "2023-04-01T12:05:23Z",
            }
        }
    )
