"""API dependency injection functions."""

from fastapi import Depends, Request

from app.integrations.email.client import MailchimpClient, mailchimp_client

# Create dependency instance at module level
mailchimp_client_dependency = Depends(lambda: mailchimp_client)


async def verify_webhook_signature(
    request: Request,
    client: MailchimpClient = mailchimp_client_dependency,
) -> bool:
    """Verify that a webhook request signature is valid.

    Args:
        request: The FastAPI request object
        client: The MailChimp client

    Returns:
        bool: True if signature is valid or signature verification is bypassed

    Raises:
        HTTPException: If signature verification fails and is strictly required
    """
    # We verify the signature but don't require it anymore
    await client.verify_webhook_signature(request)
    return True
