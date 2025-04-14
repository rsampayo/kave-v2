"""Database models for the application."""

from app.models.email_data import Attachment, Email
from app.models.organization import Organization

__all__ = ["Email", "Attachment", "Organization"]
