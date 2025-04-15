#!/usr/bin/env python
"""
Signature Verification Test Script

This script helps test webhook signature verification by:
1. Generating valid signatures using the webhook secrets in the database
2. Testing verification against those signatures
3. Providing sample cURL commands to test with real webhooks
"""

import argparse
import asyncio
import base64
import hashlib
import hmac
import json
import logging
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession

# Load environment variables first
load_dotenv()

# Then import app modules that might depend on environment variables
from app.core.config import settings  # noqa: E402
from app.db.session import get_session  # noqa: E402
from app.integrations.email.client import (  # noqa: E402
    WebhookClient,
    get_webhook_client,
)
from app.models.organization import Organization  # noqa: E402

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("test_signature")


class SignatureTester:
    """Test tool for webhook signature verification."""

    def __init__(self, db: AsyncSession, webhook_client: WebhookClient):
        """Initialize the signature tester.

        Args:
            db: Database session
            webhook_client: Webhook client
        """
        self.db = db
        self.webhook_client = webhook_client

    async def list_organizations(self) -> List[Organization]:
        """List all active organizations with their webhook secrets.

        Returns:
            List of organizations
        """
        from sqlalchemy import select

        query = select(Organization).where(Organization.is_active.is_(True))
        result = await self.db.execute(query)
        organizations = list(result.scalars().all())

        return organizations

    def generate_signature(
        self,
        webhook_secret: str,
        url: str,
        body: Dict[str, Any] | List[Dict[str, Any]] | str,
    ) -> str:
        """Generate a signature for testing.

        Args:
            webhook_secret: The webhook secret to use
            url: The webhook URL
            body: The webhook body

        Returns:
            str: Generated signature
        """
        # Start with the webhook URL
        signed_data = url

        # Handle different types of body content
        if isinstance(body, dict):
            # If it's a dictionary, sort keys and append each key+value
            for key, value in sorted(body.items()):
                signed_data += str(key)
                signed_data += str(value)
        elif isinstance(body, list):
            # For a list (array of events), convert to JSON string
            signed_data += json.dumps(body)
        else:
            # For a string or other type, just append
            signed_data += str(body)

        # Generate the signature with HMAC-SHA1 and base64 encode
        calculated_signature = base64.b64encode(
            hmac.new(
                key=webhook_secret.encode("utf-8"),
                msg=signed_data.encode("utf-8"),
                digestmod=hashlib.sha1,
            ).digest()
        ).decode("utf-8")

        return calculated_signature

    async def test_organization_verification(
        self, org_id: Optional[int] = None
    ) -> None:
        """Test signature verification for organizations.

        Args:
            org_id: Optional organization ID to test. If None, tests all organizations.
        """
        # Get organizations
        organizations = await self.list_organizations()

        if org_id:
            organizations = [org for org in organizations if org.id == org_id]
            if not organizations:
                logger.error(f"No organization found with ID {org_id}")
                return

        # Get the webhook URL
        webhook_url = settings.get_webhook_url
        logger.info(f"Using webhook URL: {webhook_url}")

        # Sample webhook body
        sample_body = {
            "webhook_id": "test-signature-verification",
            "event": "inbound_email",
            "timestamp": "2025-04-15T00:00:00Z",
            "data": {
                "message_id": "test-message-id@example.com",
                "from_email": "sender@example.com",
                "from_name": "Test Sender",
                "to_email": "webhook@example.com",
                "subject": "Test Email for Signature Verification",
                "body_plain": "This is a test email for signature verification",
                "body_html": "<p>This is a test email for signature verification</p>",
                "headers": {
                    "From": "sender@example.com",
                    "To": "webhook@example.com",
                    "Subject": "Test Email for Signature Verification",
                },
            },
        }

        # Test each organization
        for org in organizations:
            logger.info(f"Testing organization: {org.name} (ID: {org.id})")

            if not org.mandrill_webhook_secret:
                logger.warning("Organization has no webhook secret, skipping")
                continue

            # Generate signature
            signature = self.generate_signature(
                org.mandrill_webhook_secret, webhook_url, sample_body
            )

            logger.info(f"Generated signature: {signature}")

            # Test verification
            current_secret = self.webhook_client.webhook_secret
            try:
                self.webhook_client.webhook_secret = org.mandrill_webhook_secret
                is_valid = self.webhook_client.verify_signature(
                    signature, webhook_url, sample_body
                )

                if is_valid:
                    logger.info("✅ Signature verification SUCCESSFUL")
                else:
                    logger.error("❌ Signature verification FAILED")
            finally:
                self.webhook_client.webhook_secret = current_secret

            # Generate cURL command for testing
            curl_cmd = self._generate_curl_command(webhook_url, signature, sample_body)
            logger.info("Use this cURL command to test:")
            logger.info(f"  {curl_cmd}")

            logger.info("-" * 80)

    def _generate_curl_command(
        self, url: str, signature: str, body: Dict[str, Any]
    ) -> str:
        """Generate a cURL command for testing.

        Args:
            url: The webhook URL
            signature: The signature to use
            body: The webhook body

        Returns:
            str: cURL command
        """
        json_body = json.dumps(body).replace('"', '\\"')

        return (
            f"curl -X POST {url!r} "
            f'-H "Content-Type: application/json" '
            f'-H "X-Mailchimp-Signature: {signature}" '
            f"-d {json_body!r}"
        )


async def main():
    """Run the signature tester."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Test webhook signature verification")
    parser.add_argument(
        "--org", type=int, help="Organization ID to test (default: all)"
    )
    args = parser.parse_args()

    # Create DB session
    db = get_session()

    try:
        # Create webhook client
        webhook_client = get_webhook_client()

        # Create signature tester
        tester = SignatureTester(db, webhook_client)

        # Test signatures
        await tester.test_organization_verification(args.org)
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
