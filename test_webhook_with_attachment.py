import asyncio
import json
import os
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from app.db.session import Base, engine, get_db
from app.models.email_data import Attachment
from app.schemas.webhook_schemas import (
    EmailAttachment,
    InboundEmailData,
    MailchimpWebhook,
)
from app.services.email_processing_service import EmailProcessingService


async def test_webhook_with_attachment() -> None:
    """Test processing a webhook with attachment.

    Uses the email processing service directly to process a webhook with attachment.
    """  # noqa: W293
    # Load the mock webhook data
    with open("mock_webhook_with_attachment.json", "r") as f:
        webhook_data = json.load(f)

    # Convert to proper webhook schema objects
    inbound_data = InboundEmailData(
        message_id=webhook_data["data"]["message_id"],
        from_email=webhook_data["data"]["from_email"],
        from_name=webhook_data["data"]["from_name"],
        to_email=webhook_data["data"]["to_email"],
        subject=webhook_data["data"]["subject"],
        body_plain=webhook_data["data"]["body_plain"],
        body_html=webhook_data["data"]["body_html"],
        headers=webhook_data["data"]["headers"],
        attachments=[
            EmailAttachment(**a) for a in webhook_data["data"].get("attachments", [])
        ],
    )

    webhook = MailchimpWebhook(
        webhook_id=webhook_data["webhook_id"],
        event=webhook_data["event"],
        timestamp=datetime.fromisoformat(
            webhook_data["timestamp"].replace("Z", "+00:00")
        ),
        data=inbound_data,
    )

    # Create database tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Ensure attachments directory exists
    attachments_dir = Path("data/attachments")
    os.makedirs(attachments_dir, exist_ok=True)

    # Get a database session
    async for db in get_db():
        # Process the webhook
        service = EmailProcessingService(db)
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

        break


if __name__ == "__main__":
    asyncio.run(test_webhook_with_attachment())
