"""Module providing Email Data functionality for the models."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, List

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.models.attachment_text_content import (  # Import for type checking
        AttachmentTextContent,
    )
    from app.models.organization import Organization  # Import only for type checking


class Email(Base):
    """Model representing an email received from MailChimp.

    This model stores the essential data from emails received via webhooks,
    including sender information, message content, and metadata. It also
    maintains relationships with attachments.
    """

    __tablename__ = "emails"

    id: Mapped[int] = mapped_column(
        primary_key=True, index=True, comment="Unique identifier for the email record"
    )
    message_id: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        comment="Email Message-ID header, used for deduplication",
    )
    from_email: Mapped[str] = mapped_column(
        String(255), index=True, comment="Email address of the sender"
    )
    from_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="Display name of the sender, may be null"
    )
    to_email: Mapped[str] = mapped_column(
        String(255), index=True, comment="Email address of the recipient"
    )
    subject: Mapped[str] = mapped_column(
        String(255), comment="Subject line of the email"
    )
    body_text: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Plain text content of the email"
    )
    body_html: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="HTML content of the email, if available"
    )
    received_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.datetime.utcnow,
        comment="Timestamp when the email was received",
    )

    # Webhook metadata
    webhook_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="ID of the webhook that delivered this email",
    )
    webhook_event: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Type of webhook event (e.g., 'inbound_email')",
    )

    # Test column for migration example
    test_column: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Test column for Alembic migration example",
    )

    # Second test column for Alembic functionality testing
    test_column_two: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Second test column for Alembic migration testing",
    )

    # Organization relationship
    organization_id: Mapped[int | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Foreign key to the organization that sent this email",
    )

    # Relationships
    # List of attachments associated with this email
    attachments: Mapped[list["Attachment"]] = relationship(
        "Attachment", back_populates="email", cascade="all, delete-orphan"
    )

    # Reference to the organization
    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="emails"
    )


class Attachment(Base):
    """Model representing an email attachment.

    Stores metadata and content information about files attached to emails.
    The actual content is stored either in S3 (production) or the local
    filesystem (development) referenced by the storage_uri field.
    """

    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
        comment="Unique identifier for the attachment record",
    )
    email_id: Mapped[int] = mapped_column(
        ForeignKey("emails.id", ondelete="CASCADE"),
        comment="Foreign key to the parent email",
    )
    filename: Mapped[str] = mapped_column(
        String(255), comment="Original filename of the attachment"
    )
    content_type: Mapped[str] = mapped_column(
        String(100), comment="MIME type of the attachment"
    )
    content_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Content-ID for referencing in HTML (e.g., for inline images)",
    )
    size: Mapped[int | None] = mapped_column(
        nullable=True, comment="Size of the attachment in bytes"
    )

    # Storage information
    file_path: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
        comment="Path to the stored file on disk (deprecated)",
    )
    content: Mapped[bytes | None] = mapped_column(
        nullable=True,
        comment=(
            "Raw binary content of the attachment. "
            "DEPRECATED: Content should be stored in the filesystem or S3 only, "
            "referenced by storage_uri. This field is kept for backward compatibility."
        ),
    )
    storage_uri: Mapped[str | None] = mapped_column(
        String(1024),
        nullable=True,
        comment="URI for the stored file (s3:// or file:// scheme)",
    )

    # Relationship with the parent email - Reference to the parent email
    email: Mapped["Email"] = relationship("Email", back_populates="attachments")

    # Relationship with text contents from OCR - List of OCR text contents for PDF pages
    text_contents: Mapped[List["AttachmentTextContent"]] = relationship(
        "AttachmentTextContent",
        back_populates="attachment",
        cascade="all, delete-orphan",
    )


class EmailAttachment:
    """DTO for passing attachment data in API requests and tests.

    This is a non-ORM class that serves as a data transfer object for
    working with email attachments in memory, particularly during webhook
    processing or in test scenarios.
    """

    # Define slots to save memory per B903 recommendation
    __slots__ = ["name", "type", "content", "content_id", "size", "base64"]

    def __init__(
        self,
        name: str,
        type: str,
        content: str,
        content_id: str | None = None,
        size: int | None = None,
        base64: bool = True,
    ):
        """Initialize an EmailAttachment instance.

        Args:
            name: The filename of the attachment
            type: The MIME type of the attachment
            content: Base64 encoded content of the attachment (if base64=True)
                    or raw content (if base64=False)
            content_id: Optional Content-ID for inline attachments
            size: Optional size of the attachment in bytes
            base64: Whether the content is base64 encoded, defaults to True
        """
        self.name = name
        self.type = type
        self.content = content
        self.content_id = content_id
        self.size = size
        self.base64 = base64
