"""Email webhook endpoints module.

Contains FastAPI routes for handling webhook requests from MailChimp.
"""

import logging
from typing import Any, Dict, List, Union

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import verify_webhook_signature
from app.db.session import get_db
from app.integrations.email.client import MailchimpClient, get_mailchimp_client
from app.schemas.webhook_schemas import WebhookResponse
from app.services.email_service import EmailService, get_email_service

# Set up logging
logger = logging.getLogger(__name__)

# Create API router for webhooks
router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# Create dependencies
verify_signature = Depends(verify_webhook_signature)
get_db_session = Depends(get_db)
get_mailchimp = Depends(get_mailchimp_client)
get_email_handler = Depends(get_email_service)


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
        # Log the content type for debugging
        content_type = request.headers.get("content-type", "")
        logger.info(f"Mandrill webhook received with Content-Type: {content_type}")
        
        # Get the raw request body for logging
        raw_body = await request.body()
        if not raw_body:
            logger.warning("Empty request body received from Mandrill")
            return JSONResponse(
                content={"status": "error", "message": "Empty request body"},
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        
        # Log body size for debugging
        logger.debug(f"Mandrill webhook body size: {len(raw_body)} bytes")
        
        body = None
        
        # Check if we have form data (typical for Mandrill)
        if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
            logger.info("Processing Mandrill webhook as form data")
            try:
                form_data = await request.form()
                logger.debug(f"Form fields: {list(form_data.keys())}")
                
                if "mandrill_events" in form_data:
                    # This is the standard Mandrill format
                    mandrill_events = form_data["mandrill_events"]
                    logger.debug(f"Mandrill events data type: {type(mandrill_events).__name__}")
                    
                    import json
                    try:
                        body = json.loads(mandrill_events)
                        logger.info(f"Successfully parsed Mandrill events JSON. Event count: {len(body) if isinstance(body, list) else 1}")
                    except Exception as form_err:
                        logger.error(f"Failed to parse mandrill_events: {str(form_err)}")
                        return JSONResponse(
                            content={
                                "status": "error", 
                                "message": f"Invalid Mandrill webhook format: {str(form_err)}"
                            },
                            status_code=status.HTTP_400_BAD_REQUEST,
                        )
                else:
                    logger.warning(f"Mandrill form data missing 'mandrill_events' field. Available keys: {list(form_data.keys())}")
                    return JSONResponse(
                        content={
                            "status": "error", 
                            "message": "Missing 'mandrill_events' field in form data"
                        },
                        status_code=status.HTTP_400_BAD_REQUEST,
                    )
            except Exception as form_err:
                logger.error(f"Error processing form data: {str(form_err)}")
                return JSONResponse(
                    content={
                        "status": "error", 
                        "message": f"Error processing form data: {str(form_err)}"
                    },
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
        else:
            # Try parsing as JSON in case Mandrill changes their format
            logger.info("Attempting to process Mandrill webhook as direct JSON")
            try:
                body = await request.json()
                logger.debug(f"Successfully parsed JSON body: {type(body).__name__}")
            except Exception as json_err:
                logger.error(f"Failed to parse request as JSON: {str(json_err)}")
                return JSONResponse(
                    content={
                        "status": "error", 
                        "message": f"Unsupported Mandrill webhook format: {str(json_err)}"
                    },
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

        # Verify we have a body to process
        if not body:
            logger.error("No parseable body found in Mandrill webhook")
            return JSONResponse(
                content={"status": "error", "message": "No parseable body found"},
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Check if this is a ping event for webhook validation
        if isinstance(body, dict) and (body.get("type") == "ping" or body.get("event") == "ping"):
            logger.info("Received Mandrill webhook validation ping")
            return JSONResponse(
                content={
                    "status": "success",
                    "message": "Webhook validation successful",
                },
                status_code=status.HTTP_200_OK,
            )
            
        # Handle Mandrill's array-based format (standard format)
        if isinstance(body, list):
            # Mandrill sends an array of events
            event_count = len(body)
            logger.info(f"Processing {event_count} Mandrill events")
            processed_count = 0
            skipped_count = 0
            
            for event_index, event in enumerate(body):
                # Process each event
                try:
                    # Log basic event info for troubleshooting
                    event_type = event.get("event", "unknown")
                    event_id = event.get("_id", f"unknown_{event_index}")
                    logger.info(f"Processing Mandrill event {event_index+1}/{event_count}: type={event_type}, id={event_id}")
                    
                    # Format the event to match what our parse_webhook expects
                    if "msg" in event:
                        # Map 'inbound' event type to 'inbound_email' if needed
                        if event_type == "inbound":
                            event_type = "inbound_email"
                            
                        # Get message details for logging
                        msg = event.get("msg", {})
                        subject = msg.get("subject", "")[:50]  # Limit long subjects
                        from_email = msg.get("from_email", "")
                        logger.info(f"Email details - From: {from_email}, Subject: {subject}")
                        
                        # Log attachment info
                        attachments = msg.get("attachments", [])
                        if attachments:
                            attachment_info = [f"{a.get('name', 'unnamed')} ({a.get('type', 'unknown')})" for a in attachments]
                            logger.info(f"Email has {len(attachments)} attachments: {', '.join(attachment_info)}")
                        
                        # Get and process headers to convert any list values to strings
                        headers = msg.get("headers", {})
                        header_count = len(headers) if headers else 0
                        processed_headers = _process_mandrill_headers(headers)
                        
                        # Log some important headers
                        important_headers = ["message-id", "date", "to", "from", "subject"]
                        found_headers = {k: processed_headers.get(k) for k in important_headers if k.lower() in map(str.lower, processed_headers.keys())}
                        logger.debug(f"Processed {header_count} headers, important headers: {found_headers}")
                            
                        # Mandrill typically has 'msg' containing the email data
                        formatted_event = {
                            "event": event_type,
                            "webhook_id": event_id,
                            "timestamp": event.get("ts", ""),
                            "data": {
                                "message_id": msg.get("_id", ""),
                                "from_email": from_email,
                                "from_name": msg.get("from_name", ""),
                                "to_email": msg.get("email", ""),
                                "subject": subject,
                                "body_plain": msg.get("text", ""),
                                "body_html": msg.get("html", ""),
                                "headers": processed_headers,
                                "attachments": attachments,
                            }
                        }
                        
                        # Process the webhook data
                        webhook_data = await client.parse_webhook(formatted_event)
                        await email_service.process_webhook(webhook_data)
                        processed_count += 1
                        logger.info(f"Successfully processed Mandrill event {event_index+1}")
                    else:
                        logger.warning(f"Skipping Mandrill event with no msg field: event_type={event_type}, id={event_id}")
                        skipped_count += 1
                except Exception as event_err:
                    logger.error(f"Error processing Mandrill event {event_index+1}: {str(event_err)}")
                    skipped_count += 1
            
            # Return summary of processing
            if processed_count > 0:
                message = f"Processed {processed_count} events successfully"
                if skipped_count > 0:
                    message += f" ({skipped_count} skipped)"
                    
                return JSONResponse(
                    content={
                        "status": "success", 
                        "message": message
                    },
                    status_code=status.HTTP_202_ACCEPTED,
                )
            else:
                return JSONResponse(
                    content={
                        "status": "error", 
                        "message": f"Failed to process any events ({skipped_count} skipped)"
                    },
                    status_code=status.HTTP_200_OK,  # Use 200 for Mandrill to avoid retries
                )
        else:
            # Handle non-list format (unusual for Mandrill but handle it anyway)
            logger.warning("Received Mandrill webhook with non-list format, attempting to process")
            
            # Process headers if present to handle list values
            if isinstance(body, dict) and "data" in body and "headers" in body["data"]:
                body["data"]["headers"] = _process_mandrill_headers(body["data"]["headers"])
                
            webhook_data = await client.parse_webhook(body)
            await email_service.process_webhook(webhook_data)
            
            return JSONResponse(
                content={
                    "status": "success", 
                    "message": "Email processed successfully"
                },
                status_code=status.HTTP_202_ACCEPTED,
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
