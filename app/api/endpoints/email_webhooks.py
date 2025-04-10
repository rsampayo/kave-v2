"""Email webhook endpoints module.

Contains FastAPI routes for handling webhook requests from MailChimp.
"""

import logging
from typing import Any, Dict, List, Union
import time
import json
import base64
import re
import math
import string

from fastapi import APIRouter, Depends, Request, status, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import verify_webhook_signature
from app.db.session import get_db
from app.integrations.email.client import MailchimpClient, get_mailchimp_client
from app.schemas.webhook_schemas import WebhookResponse
from app.services.email_service import EmailService, get_email_service
from app.db.models import Customer

# Set up logging
logger = logging.getLogger(__name__)

# Create API router for webhooks
router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# Create dependencies
verify_signature = Depends(verify_webhook_signature)
get_db_session = Depends(get_db)
get_mailchimp = Depends(get_mailchimp_client)
get_email_handler = Depends(get_email_service)

# Add a helper function for deep redaction at the top after the imports
def _deep_redact_binary_content(data: Any, path: str = "root") -> Any:
    """
    Recursively traverse a data structure and redact any binary content.
    
    This helps prevent logging sensitive binary data (like PDF attachments)
    that could cause issues with log storage or expose PII.
    """
    # Constants for detection
    BINARY_LENGTH_THRESHOLD = 50  # Strings longer than this will be checked for binary content
    LONG_CONTENT_THRESHOLD = 200  # Extra long content will be redacted regardless
    
    # Track redaction statistics
    redaction_count = {'binary': 0, 'pdf': 0, 'long': 0, 'base64': 0}
    
    def _is_likely_binary_or_base64(s: str) -> tuple[bool, str]:
        """Check if a string appears to be binary or base64 encoded content."""
        # Quick length check first
        if len(s) < BINARY_LENGTH_THRESHOLD:
            return False, "too_short"
            
        # Check for PDF signature
        if s.startswith('%PDF-'):
            return True, "pdf_header"

        # Check for base64 characteristics (mostly alphanumeric with possibly +, /, and = padding)
        if len(s) % 4 == 0 and re.match(r'^[A-Za-z0-9+/]*={0,2}$', s):
            # Additional check: base64 strings have a particular character distribution
            uppercase = sum(1 for c in s if 'A' <= c <= 'Z')
            lowercase = sum(1 for c in s if 'a' <= c <= 'z')
            numbers = sum(1 for c in s if '0' <= c <= '9')
            special = sum(1 for c in s if c in '+/=')
            
            # Base64 should have a somewhat balanced distribution
            if uppercase + lowercase + numbers + special == len(s):
                if special <= len(s) * 0.25:  # Not too many special chars
                    return True, "base64_pattern"
            
        # Check for binary content (non-printable characters)
        binary_chars = sum(1 for c in s if c not in string.printable)
        if binary_chars > 0:
            return True, f"binary_chars_{binary_chars}"
            
        # Check if it's an unusually long string with high entropy
        if len(s) > LONG_CONTENT_THRESHOLD:
            # Calculate entropy to detect compressed or encrypted data
            char_count = {}
            for c in s:
                char_count[c] = char_count.get(c, 0) + 1
                
            entropy = 0
            for count in char_count.values():
                freq = count / len(s)
                entropy -= freq * math.log2(freq)
                
            # High entropy could indicate binary/compressed data
            if entropy > 4.5:  # Typical threshold for high entropy
                return True, f"high_entropy_{entropy:.2f}"
        
        return False, "not_binary"
        
    def _process_item(item: Any, current_path: str) -> Any:
        """Process a single item, redacting if necessary."""
        if item is None:
            return None
        
        if isinstance(item, str):
            # Handle string values - check if they could be binary/base64
            if len(item) > LONG_CONTENT_THRESHOLD:
                is_binary, reason = _is_likely_binary_or_base64(item)
                
                if is_binary:
                    if reason == "pdf_header":
                        logger.debug(f"Redacted PDF content at {current_path}, length: {len(item)}")
                        redaction_count['pdf'] += 1
                        return "[REDACTED PDF CONTENT]"
                    elif reason.startswith("binary_chars"):
                        logger.debug(f"Redacted binary content at {current_path}, length: {len(item)}, reason: {reason}")
                        redaction_count['binary'] += 1
                        return "[REDACTED BINARY CONTENT]"
                    elif reason == "base64_pattern":
                        logger.debug(f"Redacted likely base64 content at {current_path}, length: {len(item)}")
                        redaction_count['base64'] += 1
                        return "[REDACTED BASE64 CONTENT]"
                    elif reason.startswith("high_entropy"):
                        logger.debug(f"Redacted high entropy content at {current_path}, length: {len(item)}, {reason}")
                        redaction_count['binary'] += 1
                        return "[REDACTED HIGH ENTROPY CONTENT]"
                elif len(item) > LONG_CONTENT_THRESHOLD * 2:
                    # Extra-long content gets redacted even if not detected as binary
                    logger.debug(f"Redacted long text content at {current_path}, length: {len(item)}")
                    redaction_count['long'] += 1
                    return f"[REDACTED LONG CONTENT: {len(item)} CHARS]"
            
            return item
            
        elif isinstance(item, dict):
            # Process each key-value pair in the dictionary
            result = {}
            for key, value in item.items():
                # Special handling for content field in attachments
                if key == "content" and "type" in item:
                    # This is likely an attachment content field
                    
                    # For binary file types, always redact
                    content_type = item.get("type", "").lower()
                    if (content_type and any(btype in content_type for btype in [
                        "pdf", "application/", "image/", "audio/", "video/", "octet-stream"
                    ])):
                        logger.debug(f"Redacted attachment content at {current_path}, type: {content_type}")
                        result[key] = f"[REDACTED {content_type.upper()} CONTENT]"
                        redaction_count['binary'] += 1
                    else:
                        # Process normally if it's not a known binary type
                        new_path = f"{current_path}.{key}"
                        result[key] = _process_item(value, new_path)
                else:
                    # Process normally
                    new_path = f"{current_path}.{key}"
                    result[key] = _process_item(value, new_path)
            return result
            
        elif isinstance(item, list):
            # Process each item in the list
            result = []
            for i, list_item in enumerate(item):
                new_path = f"{current_path}[{i}]"
                result.append(_process_item(list_item, new_path))
            return result
            
        else:
            # Return non-container types as-is
            return item
    
    # Process the entire data structure
    result = _process_item(data, path)
    
    # Log the redaction statistics if any redactions were made
    total_redactions = sum(redaction_count.values())
    if total_redactions > 0:
        logger.info(f"Redaction summary: {total_redactions} items redacted - "
                   f"PDF: {redaction_count['pdf']}, Binary: {redaction_count['binary']}, "
                   f"Base64: {redaction_count['base64']}, Long: {redaction_count['long']}")
    
    return result


@router.head(
    "/mailchimp",
    status_code=status.HTTP_200_OK,
    summary="Handle MailChimp webhook validation (HEAD request)",
    description=(
        "MailChimp sends a HEAD request to validate the webhook URL "
        "before sending POST data. "
        "This endpoint acknowledges the HEAD request."
    ),
    include_in_schema=False,  # Hide from OpenAPI docs as it's for validation
)
async def head_mailchimp_webhook() -> None:
    """Acknowledge MailChimp's HEAD request for webhook validation."""
    return None


@router.post(
    "/mailchimp",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Receive MailChimp email webhook",
    description=(
        "Endpoint for MailChimp to send email data via webhook. "
        "Processes incoming emails, extracts data, "
        "and stores them in the database."
    ),
    response_model=WebhookResponse,
    responses={
        status.HTTP_202_ACCEPTED: {
            "description": "Webhook received and processed successfully",
            "model": WebhookResponse,
            "content": {
                "application/json": {
                    "example": {
                        "status": "success",
                        "message": "Email processed successfully",
                    }
                }
            },
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "An error occurred while processing the webhook",
            "model": WebhookResponse,
            "content": {
                "application/json": {
                    "example": {
                        "status": "error",
                        "message": "Failed to process webhook: Invalid data format",
                    }
                }
            },
        },
    },
)
async def receive_mailchimp_webhook(
    request: Request,
    db: AsyncSession = get_db_session,
    _: bool = verify_signature,
    email_service: EmailService = get_email_handler,
    client: MailchimpClient = get_mailchimp,
) -> JSONResponse:
    """Handle MailChimp email webhook.

    This endpoint receives webhooks from MailChimp containing email data.
    It validates the webhook signature, processes the email content including
    any attachments, and stores the data in the database.

    Args:
        request: The FastAPI request object containing the webhook payload
        db: Database session for persistence operations
        _: Dependency to verify webhook signature (automatically checks auth)
        email_service: Service for processing email data
        client: MailChimp client for webhook parsing

    Returns:
        JSONResponse: Success response with appropriate status code:
            - 200 OK for ping events during webhook registration
            - 202 ACCEPTED for regular webhook events
            - 500 INTERNAL SERVER ERROR for processing errors

    Raises:
        HTTPException: If parsing fails
    """
    try:
        # First try to get the raw request body as text to validate it's not empty
        raw_body = await request.body()
        if not raw_body:
            return JSONResponse(
                content={"status": "error", "message": "Empty request body"},
                status_code=status.HTTP_400_BAD_REQUEST,
            )
            
        # Log the raw body for debugging
        logger.debug(f"Raw Mailchimp webhook body: {raw_body}")
        
        # Try to parse the JSON body
        try:
            body = await request.json()
        except Exception as json_err:
            logger.error(f"Failed to parse Mailchimp webhook JSON: {str(json_err)}")
            return JSONResponse(
                content={
                    "status": "error", 
                    "message": f"Invalid JSON format: {str(json_err)}"
                },
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Check if this is a ping event for webhook validation
        if body.get("type") == "ping" or body.get("event") == "ping":
            logger.info("Received Mailchimp webhook validation ping")
            return JSONResponse(
                content={
                    "status": "success",
                    "message": "Webhook validation successful",
                },
                status_code=status.HTTP_200_OK,
            )

        # Parse webhook data for regular events
        # Pass the already parsed body to avoid parsing it twice
        webhook_data = await client.parse_webhook(body)

        # Process the webhook
        await email_service.process_webhook(webhook_data)

        return JSONResponse(
            content={"status": "success", "message": "Email processed successfully"},
            status_code=status.HTTP_202_ACCEPTED,
        )
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        # Note: Returning 500 for internal errors, though Mailchimp might prefer 2xx
        return JSONResponse(
            content={
                "status": "error",
                "message": f"Failed to process webhook: {str(e)}",
            },
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


def _process_mandrill_headers(headers: Dict[str, Any]) -> Dict[str, str]:
    """Process Mandrill headers to ensure they're all strings.
    
    Mandrill may send headers as lists of strings, but our schema expects Dict[str, str].
    This function converts any list values to strings by joining them.
    
    Args:
        headers: The raw headers from Mandrill
        
    Returns:
        Dict[str, str]: Headers with all values as strings
    """
    processed_headers = {}
    for key, value in headers.items():
        if isinstance(value, list):
            # Join list values with a newline for readability
            processed_headers[key] = "\n".join(value)
        else:
            processed_headers[key] = str(value)
    return processed_headers


@router.post(
    "/mandrill",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Receive Mandrill email webhook",
    description=(
        "Endpoint for Mandrill to send email data via webhook. "
        "Processes incoming emails, extracts data, "
        "and stores them in the database."
    ),
    response_model=WebhookResponse,
    responses={
        status.HTTP_202_ACCEPTED: {
            "description": "Webhook received and processed successfully",
            "model": WebhookResponse,
            "content": {
                "application/json": {
                    "example": {
                        "status": "success",
                        "message": "Email processed successfully",
                    }
                }
            },
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "An error occurred while processing the webhook",
            "model": WebhookResponse,
            "content": {
                "application/json": {
                    "example": {
                        "status": "error",
                        "message": "Failed to process webhook: Invalid data format",
                    }
                }
            },
        },
    },
)
async def receive_mandrill_webhook(
    request: Request,
    db: AsyncSession = get_db_session,
    _: bool = verify_signature,
    email_service: EmailService = get_email_handler,
    client: MailchimpClient = get_mailchimp,
) -> JSONResponse:
    """Handle Mandrill email webhook.

    This endpoint receives webhooks from Mandrill containing email data.
    Mandrill typically sends data as form data with a field named 'mandrill_events'
    containing a JSON string with an array of events.

    Args:
        request: The FastAPI request object containing the webhook payload
        db: Database session for persistence operations
        _: Dependency to verify webhook signature (automatically checks auth)
        email_service: Service for processing email data
        client: MailChimp client for webhook parsing

    Returns:
        JSONResponse: Success response with appropriate status code:
            - 200 OK for ping events during webhook registration
            - 202 ACCEPTED for regular webhook events
            - 500 INTERNAL SERVER ERROR for processing errors
    """
    try:
        logger.info("Received Mandrill webhook")
        # Parse the webhook data
        form_data = await request.form()
        mandrill_events = json.loads(form_data.get("mandrill_events", "[]"))
        
        if not mandrill_events:
            logger.warning("Empty Mandrill webhook event")
            return {"status": "success"}
        
        logger.info(f"Processing {len(mandrill_events)} Mandrill events")
        
        # Track overall attachment processing statistics
        attachment_stats = {
            "total": 0,
            "success": 0,
            "errors": 0,
            "dict_format": 0,
            "list_format": 0,
            "skipped": 0
        }
        
        # Process each event
        for event_idx, event in enumerate(mandrill_events):
            # Log the event type
            event_type = event.get("event")
            msg = event.get("msg", {})
            sender = msg.get("sender", "unknown")
            recipient = msg.get("email", "unknown")
            subject = msg.get("subject", "no subject")
            
            logger.info(f"Event {event_idx+1}/{len(mandrill_events)}: Type: {event_type}, From: {sender}, To: {recipient}, Subject: {subject}")
            
            # Redact any potential binary content before logging
            safe_event = _deep_redact_binary_content(event)
            logger.debug(f"Mandrill event data: {safe_event}")
            
            # Process the message
            try:
                # Extract basic email information
                email = msg.get("email", "")
                subject = msg.get("subject", "")
                
                if not email:
                    logger.warning("Missing email address in Mandrill webhook")
                    continue
                
                logger.info(f"Processing email for {email}, subject: {subject}")
                
                # Get the customer for this email
                customer = db.query(Customer).filter(
                    Customer.email == email
                ).first()
                
                if not customer:
                    logger.warning(f"Customer not found for email: {email}")
                    continue
                
                # Process attachments if any
                attachments = msg.get("attachments", [])
                parsed_attachments = []
                
                # Log attachment details for debugging
                attachment_stats["total"] += (len(attachments) if isinstance(attachments, list) else 
                                            len(attachments.keys()) if isinstance(attachments, dict) else 0)
                
                if attachments:
                    if isinstance(attachments, dict):
                        attachment_stats["dict_format"] += 1
                        logger.info(f"Processing dictionary format attachments with {len(attachments)} items")
                        logger.debug(f"Attachment keys: {list(attachments.keys())}")
                    elif isinstance(attachments, list):
                        attachment_stats["list_format"] += 1
                        logger.info(f"Processing list format attachments with {len(attachments)} items")
                    else:
                        logger.warning(f"Received unexpected attachment format: {type(attachments)}")
                
                # Handle attachments - could be a dict or a list depending on Mandrill's format
                if isinstance(attachments, dict):
                    # Dictionary format where keys are filenames
                    for filename, attachment_data in attachments.items():
                        logger.debug(f"Processing attachment: {filename}")
                        
                        # Check that we have the expected fields
                        if isinstance(attachment_data, dict) and "content" in attachment_data:
                            # Some fields may be missing, so set defaults
                            content = attachment_data.get("content", "")
                            content_type = attachment_data.get("type", "application/octet-stream")
                            
                            # Ensure we have a name
                            name = attachment_data.get("name", filename)
                            
                            try:
                                # Decode content if it's base64
                                content_bytes = base64.b64decode(content)
                                parsed_attachments.append({
                                    "name": name,
                                    "type": content_type,
                                    "content": content_bytes
                                })
                                logger.info(f"Successfully processed attachment: {name} ({content_type}), size: {len(content_bytes)} bytes")
                                attachment_stats["success"] += 1
                            except Exception as e:
                                logger.error(f"Error decoding attachment {name}: {str(e)}")
                                attachment_stats["errors"] += 1
                        else:
                            logger.warning(f"Skipping attachment {filename} - missing required fields")
                            attachment_stats["skipped"] += 1
                    
                    logger.info(f"Processed {len(parsed_attachments)}/{len(attachments)} attachments from dictionary format")
                
                elif isinstance(attachments, list):
                    # List format of attachment objects
                    for attachment in attachments:
                        if not isinstance(attachment, dict):
                            logger.warning(f"Skipping non-dict attachment: {type(attachment)}")
                            attachment_stats["skipped"] += 1
                            continue
                            
                        logger.debug(f"Processing list attachment: {attachment.get('name', 'unnamed')}")
                        
                        # Ensure we have the necessary fields
                        if "content" in attachment and "name" in attachment:
                            try:
                                content = attachment.get("content", "")
                                content_type = attachment.get("type", "application/octet-stream")
                                name = attachment.get("name", "attachment")
                                
                                # Decode content if it's base64
                                content_bytes = base64.b64decode(content)
                                parsed_attachments.append({
                                    "name": name,
                                    "type": content_type,
                                    "content": content_bytes
                                })
                                logger.info(f"Successfully processed list attachment: {name} ({content_type}), size: {len(content_bytes)} bytes")
                                attachment_stats["success"] += 1
                            except Exception as e:
                                logger.error(f"Error decoding list attachment {attachment.get('name', 'unnamed')}: {str(e)}")
                                attachment_stats["errors"] += 1
                        else:
                            missing_fields = set(["content", "name"]) - set(attachment.keys())
                            logger.warning(f"Skipping list attachment - missing required fields: {missing_fields}")
                            attachment_stats["skipped"] += 1
                    
                    logger.info(f"Processed {len(parsed_attachments)}/{len(attachments)} attachments from list format")
                
                elif attachments:  # Not empty but wrong type
                    logger.warning(f"Unexpected attachment format: {type(attachments)}")
                
                # Create email record in database
                # ... rest of the processing

            except Exception as event_err:
                logger.error(f"Error processing Mandrill event: {str(event_err)}")
                continue
        
        # Log attachment processing summary
        if attachment_stats["total"] > 0:
            logger.info(
                f"Attachment processing summary: "
                f"Total: {attachment_stats['total']}, "
                f"Success: {attachment_stats['success']}, "
                f"Errors: {attachment_stats['errors']}, "
                f"Skipped: {attachment_stats['skipped']}, "
                f"Dict format events: {attachment_stats['dict_format']}, "
                f"List format events: {attachment_stats['list_format']}"
            )
        
        return JSONResponse(
            content={
                "status": "success", 
                "message": "Email processed successfully"
            },
            status_code=status.HTTP_202_ACCEPTED,
        )
    except json.JSONDecodeError as json_err:
        logger.error(f"Invalid JSON in Mandrill webhook: {str(json_err)}")
        return JSONResponse(
            content={
                "status": "error",
                "message": f"Invalid JSON format: {str(json_err)}",
            },
            status_code=status.HTTP_200_OK,  # Still return 200 for Mandrill
        )
    except Exception as e:
        logger.error(f"Error processing Mandrill webhook: {str(e)}")
        # Return 200 OK even for errors as Mandrill expects 2xx responses
        # to avoid retry attempts
        return JSONResponse(
            content={
                "status": "error",
                "message": f"Failed to process webhook but acknowledged: {str(e)}",
            },
            status_code=status.HTTP_200_OK,
        )
