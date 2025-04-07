import asyncio
import json
from datetime import datetime

from app.db.session import Base, engine, get_db
from app.schemas.webhook_schemas import (
    EmailAttachment,
    InboundEmailData,
    MailchimpWebhook,
)
from app.services.email_processing_service import EmailProcessingService


async def test_webhook() -> None:
    """Test processing a webhook directly using the email processing service."""
    # Load the mock webhook data
    with open("mock_webhook.json", "r") as f:
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

        break


if __name__ == "__main__":
    asyncio.run(test_webhook())
