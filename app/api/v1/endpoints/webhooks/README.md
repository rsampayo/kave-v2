# Email Webhook System

This directory contains the implementation of the webhook system for processing email-related events from various providers.

## Architecture

The webhook system is organized in a modular, provider-specific structure:

```
webhooks/
├── common/              # Shared utilities used across providers
│   ├── attachments.py   # Attachment processing utilities
│   └── mime_utils.py    # MIME decoding utilities
├── mandrill/            # Mandrill-specific implementation
│   ├── formatters.py    # Format Mandrill events to our standard format
│   ├── parsers.py       # Parse Mandrill webhook requests
│   ├── processors.py    # Process Mandrill events
│   └── router.py        # FastAPI router for Mandrill endpoints
└── [provider]/          # Future providers (e.g., Twilio, SendGrid)
    ├── formatters.py
    ├── parsers.py
    ├── processors.py
    └── router.py
```

## Adding a New Webhook Provider

To add support for a new webhook provider (e.g., Twilio, SendGrid), follow these steps:

1. **Create a Provider Directory**
   - Create a new directory under `webhooks/` with the provider name
   - Add an `__init__.py` file to make it a proper package

2. **Implement Core Modules**
   Each provider should implement these modules with provider-specific logic:

   - `parsers.py`: Functions to parse and validate incoming webhook requests
   - `formatters.py`: Functions to convert provider-specific formats to our standard format
   - `processors.py`: Functions to process the normalized events
   - `router.py`: FastAPI router defining the endpoints for this provider

3. **Create Provider Router**
   - Implement a router in `router.py` that defines the provider's endpoints
   - Example:
     ```python
     router = APIRouter()
     
     @router.post(
        "",
        status_code=status.HTTP_202_ACCEPTED,
        summary="Receive [Provider] webhook",
        response_model=WebhookResponse,
     )
     async def receive_provider_webhook(request: Request, ...): 
         # Provider-specific implementation
         ...
     ```

4. **Register the Provider Router**
   - Update `app/api/endpoints/email_webhooks.py` to include your new router:
     ```python
     from app.api.endpoints.webhooks.provider.router import router as provider_router
     
     # Include the provider router
     router.include_router(
         provider_router,
         prefix="/provider",
     )
     ```

5. **Reuse Common Utilities**
   - Leverage the utilities in the `common/` directory for shared functionality
   - Create new common utilities if needed for multiple providers

## Integration Requirements

When implementing a new provider, ensure your implementation:

1. Returns appropriate HTTP status codes (typically 200/202 for success)
2. Uses the `WebhookResponse` schema for consistent response formats
3. Properly validates incoming requests
4. Handles special cases like ping/validation events
5. Normalizes provider-specific fields to match our internal data model
6. Logs appropriate information for monitoring and debugging

## Testing

Each new provider should have:

1. Unit tests for individual functions (parsers, formatters, processors)
2. Integration tests for the complete webhook flow
3. Test fixtures representing real webhook payloads from the provider 