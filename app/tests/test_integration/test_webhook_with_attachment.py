"""Module providing Test Webhook With Attachment functionality for the tests test integration."""

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import select

from app.db.session import Base, engine, get_session
from app.models.email_data import Attachment
from app.schemas.webhook_schemas import (
    EmailAttachment,
    InboundEmailData,
    MailchimpWebhook,
)
from app.services.email_processing_service import EmailProcessingService
from app.services.storage_service import StorageService


@pytest.mark.asyncio
async def test_webhook_with_attachment() -> None:
    """Test processing a webhook with attachment.

    Uses the email processing service directly to process a webhook with attachment.
    """  # noqa: W293
    # Load the mock webhook data
    with open("app/tests/test_data/mock_webhook_with_attachment.json") as f:
        webhook_data = json.load(f)

    mandrill_event = webhook_data["mandrill_events"][0]
    message = mandrill_event["msg"]

    # Convert Mandrill headers format (which can have lists) to our expected format (simple dict)
    headers = {}
    for key, value in message["headers"].items():
        # If header value is a list, join it with commas
        if isinstance(value, list):
            headers[key] = ", ".join(value)
        else:
            headers[key] = value

    # Extract attachment data from Mandrill format
    attachments = []
    if "attachments" in message and message["attachments"]:
        for att_key, att_data in message["attachments"].items():
            attachments.append(
                EmailAttachment(
                    name=att_data["name"],
                    type=att_data["type"],
                    content=att_data["content"],
                    content_id=att_key,
                    size=len(att_data["content"]) if "content" in att_data else 0,
                    base64=True,
                )
            )

    # Convert Mandrill format to our internal schema
    inbound_data = InboundEmailData(
        message_id=message["_id"],
        from_email=message["from_email"],
        from_name=message["from_name"],
        to_email=message["email"],
        subject=message["subject"],
        body_plain=message["text"],
        body_html=message["html"],
        headers=headers,
        attachments=attachments,
    )

    # Create a webhook object with the converted data
    webhook = MailchimpWebhook(
        webhook_id=message["_id"],
        event=mandrill_event["event"],
        timestamp=datetime.fromtimestamp(mandrill_event["ts"], tz=timezone.utc),
        data=inbound_data,
    )

    # Create database tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Ensure attachments directory exists
    attachments_dir = Path("data/attachments")
    os.makedirs(attachments_dir, exist_ok=True)

    # Use direct session creation instead of get_db async generator
    # This avoids issues with asyncio task cleanup
    db = get_session()
    try:
        # Process the webhook
        storage_service = StorageService()
        service = EmailProcessingService(db, storage_service)
        email = await service.process_webhook(webhook)

        # Check the result
        print("Email processed successfully:")
        print(f"  ID: {email.id}")
        print(f"  Message ID: {email.message_id}")
        print(f"  From: {email.from_name} <{email.from_email}>")
        print(f"  To: {email.to_email}")
        print(f"  Subject: {email.subject}")
        print(f"  Webhook ID: {email.webhook_id}")
        print(f"  Webhook Event: {email.webhook_event}")
        print(f"  Received at: {email.received_at}")

        # Check for attachments - use SQLAlchemy async API
        query = select(Attachment).where(Attachment.email_id == email.id)
        result = await db.execute(query)
        attachments_list = result.scalars().all()

        print(f"\nAttachments ({len(attachments_list)}):")
        for att in attachments_list:
            print(f"  - {att.filename} ({att.content_type}, {att.size} bytes)")
            print(f"    Stored at: {att.file_path}")

            # Check if the file exists
            if att.file_path and os.path.exists(att.file_path):
                print("    File exists: Yes")
                # Read the first 50 characters of the file content
                with open(att.file_path, "rb") as f:
                    content = f.read(50)
                    print(f"    Content preview: {content!r}...")
            else:
                print("    File exists: No")

        await db.commit()
    except Exception as e:
        await db.rollback()
        raise e
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(test_webhook_with_attachment())
