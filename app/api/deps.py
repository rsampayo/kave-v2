"""API dependency injection functions."""

from fastapi import Depends, HTTPException, Request, status

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
        bool: True if signature is valid

    Raises:
        HTTPException: If signature verification fails
    """
    is_valid = await client.verify_webhook_signature(request)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature",
        )
    return True
