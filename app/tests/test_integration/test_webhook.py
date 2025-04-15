"""Module providing Test Webhook functionality for the tests test integration."""

import asyncio
import json
from datetime import datetime, timezone

import pytest

from app.db.session import Base, engine, get_session
from app.schemas.webhook_schemas import InboundEmailData, MailchimpWebhook
from app.services.email_processing_service import EmailProcessingService
from app.services.storage_service import StorageService


@pytest.mark.asyncio
async def test_webhook() -> None:
    """Test processing a webhook directly using the email processing service."""
    # Load the mock webhook data
    with open("app/tests/test_data/mock_webhook.json") as f:
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
        attachments=[],  # No attachments in this test
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

        await db.commit()
    except Exception as e:
        await db.rollback()
        raise e
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(test_webhook())
