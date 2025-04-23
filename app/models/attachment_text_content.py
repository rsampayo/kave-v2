"""Module providing AttachmentTextContent model for OCR extracted text from PDF attachments."""

from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.models.email_data import Attachment


class AttachmentTextContent(Base):
    """
    Stores OCR-extracted text content from PDF attachments, page by page.

    This model maintains a one-to-many relationship with the Attachment model,
    where each record represents the text content of a single page from a PDF attachment.
    """

    __tablename__ = "attachment_text_content"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    attachment_id: Mapped[int] = mapped_column(
        ForeignKey("attachments.id", ondelete="CASCADE"), index=True
    )
    page_number: Mapped[int] = mapped_column(nullable=False)
    text_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationship back to Attachment
    attachment: Mapped["Attachment"] = relationship(
        "Attachment", back_populates="text_contents"
    )
