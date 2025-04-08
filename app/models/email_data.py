from datetime import datetime
from typing import List, Optional

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


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
    from_name: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="Display name of the sender, may be null"
    )
    to_email: Mapped[str] = mapped_column(
        String(255), index=True, comment="Email address of the recipient"
    )
    subject: Mapped[str] = mapped_column(
        String(255), comment="Subject line of the email"
    )
    body_text: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="Plain text content of the email"
    )
    body_html: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="HTML content of the email, if available"
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        comment="Timestamp when the email was received",
    )

    # Webhook metadata
    webhook_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="ID of the webhook that delivered this email",
    )
    webhook_event: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Type of webhook event (e.g., 'inbound_email')",
    )

    # Relationships - List of attachments associated with this email
    attachments: Mapped[List["Attachment"]] = relationship(
        "Attachment", back_populates="email", cascade="all, delete-orphan"
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
    content_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Content-ID for referencing in HTML (e.g., for inline images)",
    )
    size: Mapped[Optional[int]] = mapped_column(
        nullable=True, comment="Size of the attachment in bytes"
    )

    # Storage information
    file_path: Mapped[Optional[str]] = mapped_column(
        String(512),
        nullable=True,
        comment="Path to the stored file on disk (deprecated)",
    )
    content: Mapped[Optional[bytes]] = mapped_column(
        nullable=True,
        comment=(
            "Raw binary content of the attachment. "
            "DEPRECATED: Content should be stored in the filesystem or S3 only, "
            "referenced by storage_uri. This field is kept for backward compatibility."
        ),
    )
    storage_uri: Mapped[Optional[str]] = mapped_column(
        String(1024),
        nullable=True,
        comment="URI for the stored file (s3:// or file:// scheme)",
    )

    # Relationship with the parent email - Reference to the parent email
    email: Mapped["Email"] = relationship("Email", back_populates="attachments")


class EmailAttachment:
    """DTO for passing attachment data in API requests and tests.

    This is a non-ORM class that serves as a data transfer object for
    working with email attachments in memory, particularly during webhook
    processing or in test scenarios.
    """

    # Define slots to save memory per B903 recommendation
    __slots__ = ["name", "type", "content", "content_id", "size"]

    def __init__(
        self,
        name: str,
        type: str,
        content: str,
        content_id: Optional[str] = None,
        size: Optional[int] = None,
    ):
        """Initialize an EmailAttachment instance.

        Args:
            name: The filename of the attachment
            type: The MIME type of the attachment
            content: Base64 encoded content of the attachment
            content_id: Optional Content-ID for inline attachments
            size: Optional size of the attachment in bytes
        """
        self.name = name
        self.type = type
        self.content = content  # Base64 encoded content
        self.content_id = content_id
        self.size = size
