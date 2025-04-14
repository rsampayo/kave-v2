"""Module providing Organization model functionality."""

from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.email_data import Email


class Organization(Base):
    """Model representing an organization for webhook configuration.

    This model stores the details of organizations that can send webhooks,
    including the organization name, sending email, and Mandrill API credentials.
    This allows the system to identify which organization sent each email/webhook.
    """

    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(
        primary_key=True, index=True, comment="Unique identifier for the organization"
    )
    name: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, comment="Name of the organization"
    )
    webhook_email: Mapped[str] = mapped_column(
        String(255), index=True, comment="Email address that will be sending webhooks"
    )
    mandrill_api_key: Mapped[str] = mapped_column(
        String(255), comment="Mandrill API key for this organization"
    )
    mandrill_webhook_secret: Mapped[str] = mapped_column(
        String(255), comment="Mandrill webhook secret for this organization"
    )
    is_active: Mapped[bool] = mapped_column(
        default=True, comment="Whether this organization's webhooks are active"
    )

    # Relationship with emails - List of emails associated with this organization
    emails: Mapped[list["Email"]] = relationship(
        "Email", back_populates="organization", cascade="all, delete-orphan"
    )
