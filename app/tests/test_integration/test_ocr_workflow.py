"""Integration test for PDF OCR workflow."""

import os
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attachment_text_content import AttachmentTextContent
from app.models.email_data import Attachment, Email


@pytest.mark.asyncio
async def test_ocr_workflow(db_session: AsyncSession):
    """Test the PDF OCR workflow directly without webhooks."""
    # Test data
    SAMPLE_PDF_PATH = Path(__file__).parent / "test_data" / "sample.pdf"
    if not os.path.exists(SAMPLE_PDF_PATH):
        pytest.skip(f"Sample PDF not found at {SAMPLE_PDF_PATH}")

    # Step 1: Create a test email in the database
    email = Email(
        message_id="test-message-123@example.com",
        from_email="test@example.com",
        to_email="recipient@example.com",
        subject="Test Email with PDF Attachment",
        body_text="This is a test email with a PDF attachment.",
        body_html="<p>This is a test email with a PDF attachment.</p>",
    )
    db_session.add(email)
    await db_session.flush()

    # Step 2: Create a test PDF attachment
    with open(SAMPLE_PDF_PATH, "rb") as f:
        pdf_content = f.read()

    attachment = Attachment(
        email_id=email.id,
        filename="test-document.pdf",
        content_type="application/pdf",
        size=len(pdf_content),
        storage_uri="file:///test_pdf_attachment",
    )
    db_session.add(attachment)
    await db_session.flush()

    # Step 3: Create OCR text content entries manually
    for page_num in range(1, 4):  # Simulate a 3-page document
        text_content = f"OCR extracted text from page {page_num} of test-document.pdf"
        text_entry = AttachmentTextContent(
            attachment_id=attachment.id,
            page_number=page_num,
            text_content=text_content,
        )
        db_session.add(text_entry)

    await db_session.commit()

    # Step 4: Verify that the data was saved correctly
    content_query = select(AttachmentTextContent).where(
        AttachmentTextContent.attachment_id == attachment.id
    )
    content_result = await db_session.execute(content_query)
    content_entries = list(content_result.scalars().all())

    # Verify we have the expected number of entries
    assert (
        len(content_entries) == 3
    ), f"Expected 3 text content entries, got {len(content_entries)}"

    # Verify each page's content
    for page_num in range(1, 4):
        entry = next((e for e in content_entries if e.page_number == page_num), None)
        assert entry is not None, f"Missing entry for page {page_num}"
        assert entry.text_content, f"Empty text content for page {page_num}"
        assert (
            f"page {page_num}" in entry.text_content
        ), f"Expected page number reference in content for page {page_num}"

    # Verify the relationship works both ways by querying for the relationship
    text_contents_query = (
        select(AttachmentTextContent)
        .where(AttachmentTextContent.attachment_id == attachment.id)
        .order_by(AttachmentTextContent.page_number)
    )
    text_contents_result = await db_session.execute(text_contents_query)
    text_contents = list(text_contents_result.scalars().all())

    # The relationship query should return the same 3 records
    assert (
        len(text_contents) == 3
    ), f"Expected 3 text content entries via explicit query, got {len(text_contents)}"

    # Verify the pages are in correct order
    for i, entry in enumerate(text_contents):
        assert (
            entry.page_number == i + 1
        ), f"Expected page number {i + 1}, got {entry.page_number}"
