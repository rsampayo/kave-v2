# Mailchimp Webhook Signature Verification Implementation Plan V2

## Overview

This plan outlines the implementation of Mailchimp webhook signature verification for the Kave application. The implementation will be performed iteratively, with each step tracked in `signature_implementation_tracker.json`. This plan supports:

1. Verification of webhook authenticity using HMAC-SHA1 signatures
2. Organization identification based on signatures
3. Environment-aware webhook processing (production vs. testing)
4. Organization-specific webhook configuration

## Implementation Workflow

For each implementation step:

1. Update `current_step` in the tracker file
2. Change the sub-task status to `in_progress`
3. Implement the required code changes
4. Write/update the corresponding tests
5. Run tests and fix any issues
6. Run code quality checks (black, isort, flake8, mypy)
7. Update sub-task status to `completed`
8. Move to the next sub-task

## Step 1: Environment Configuration Updates

### Sub-task 1.1: Update .env file

```
# Update .env file with new webhook URL configurations
# Webhook Base URLs (required)
MAILCHIMP_WEBHOOK_BASE_URL_PRODUCTION=https://api.example.com
MAILCHIMP_WEBHOOK_BASE_URL_TESTING=https://dev.example.com

# Webhook Path (remains the same across environments)
WEBHOOK_PATH=/v1/webhooks/mandrill

# Verification Configuration
MAILCHIMP_REJECT_UNVERIFIED_PRODUCTION=false
MAILCHIMP_REJECT_UNVERIFIED_TESTING=false

# Webhook Environment Mode (testing or production)
MAILCHIMP_WEBHOOK_ENVIRONMENT=testing
```

* **File**: `.env`
* **Tests**: N/A (environment configuration)
* **Tracker Update**: Set sub-task 1.1 status to `completed`

### Sub-task 1.2: Update Settings class

Add properties to the `Settings` class in `app/core/config.py`:

```python
# Add to existing Settings class
MAILCHIMP_WEBHOOK_BASE_URL_PRODUCTION: str = ""
MAILCHIMP_WEBHOOK_BASE_URL_TESTING: str = ""
WEBHOOK_PATH: str = "/v1/webhooks/mandrill"
MAILCHIMP_REJECT_UNVERIFIED_PRODUCTION: bool = False
MAILCHIMP_REJECT_UNVERIFIED_TESTING: bool = False
MAILCHIMP_WEBHOOK_ENVIRONMENT: str = "testing"  # Options: "production", "testing"

@property
def get_webhook_url(self) -> str:
    """Get the full webhook URL for the current environment.
    
    Returns:
        str: The complete webhook URL for the current environment
    """
    base_url = (
        self.MAILCHIMP_WEBHOOK_BASE_URL_PRODUCTION 
        if self.is_production_environment 
        else self.MAILCHIMP_WEBHOOK_BASE_URL_TESTING
    )
    
    # Ensure the base URL doesn't end with a slash and path starts with one
    path = self.WEBHOOK_PATH
    if not path.startswith("/"):
        path = f"/{path}"
        
    return f"{base_url}{path}"
```

* **File**: `app/core/config.py`
* **Tests**: `app/tests/test_unit/test_core/test_config.py::test_get_webhook_url_property`
* **Tracker Update**: Set sub-task 1.2 status to `completed`

### Sub-task 1.3: Add environment detection settings

Add environment detection properties to the `Settings` class:

```python
@property
def is_production_environment(self) -> bool:
    """Determine if we're running in a production environment.
    
    Returns:
        bool: True if in production or staging
    """
    return self.API_ENV in ("production", "staging")
    
@property
def should_reject_unverified(self) -> bool:
    """Determine if unverified webhooks should be rejected.
    
    Returns:
        bool: True if unverified webhooks should be rejected
    """
    if self.is_production_environment:
        return self.MAILCHIMP_REJECT_UNVERIFIED_PRODUCTION
    return self.MAILCHIMP_REJECT_UNVERIFIED_TESTING
```

* **File**: `app/core/config.py`
* **Tests**: N/A (covered by previous test)
* **Tracker Update**: 
  * Set sub-task 1.3 status to `completed`
  * Set Step 1 status to `completed`
  * Update `current_step` to 2

## Step 2: WebhookClient Enhancements

### Sub-task 2.1: Implement verify_signature method

Add signature verification to the WebhookClient:

```python
import base64
import hmac
import hashlib

def verify_signature(
    self, 
    signature: str, 
    url: str, 
    params: dict[str, Any]
) -> bool:
    """Verify a webhook signature from Mailchimp.
    
    Args:
        signature: The X-Mailchimp-Signature header value
        url: The webhook URL (as registered with Mailchimp)
        params: The request parameters (POST body)
        
    Returns:
        bool: True if the signature is valid, False otherwise
    """
    # Start with the webhook URL
    signed_data = url
    
    # Handle different types of body content
    if isinstance(params, dict):
        # If it's a dictionary, sort keys and append each key+value
        for key, value in sorted(params.items()):
            signed_data += str(key)
            signed_data += str(value)
    elif isinstance(params, list):
        # For a list (array of events), convert to JSON string
        import json
        signed_data += json.dumps(params)
    else:
        # For a string or other type, just append
        signed_data += str(params)
    
    # Generate the signature with HMAC-SHA1 and base64 encode
    calculated_signature = base64.b64encode(
        hmac.new(
            key=self.webhook_secret.encode("utf-8"),
            msg=signed_data.encode("utf-8"),
            digestmod=hashlib.sha1
        ).digest()
    ).decode("utf-8")
    
    # Compare signatures
    return calculated_signature == signature
```

* **File**: `app/integrations/email/client.py`
* **Tests**: 
  * `app/tests/test_unit/test_integrations/test_email_client.py::test_verify_signature_valid`
  * `app/tests/test_unit/test_integrations/test_email_client.py::test_verify_signature_invalid`
* **Tracker Update**: Set sub-task 2.1 status to `completed`

### Sub-task 2.2: Implement identify_organization_by_signature method

Add organization identification by signature:

```python
async def identify_organization_by_signature(
    self, 
    signature: str, 
    url: str, 
    body: dict[str, Any] | list[dict[str, Any]] | str,
    db: AsyncSession
) -> tuple[Organization | None, bool]:
    """Identify the organization by webhook signature.
    
    Args:
        signature: The X-Mailchimp-Signature header value
        url: The webhook URL
        body: The webhook body
        db: Database session
        
    Returns:
        tuple: (Organization or None, was_verified)
    """
    # If no signature provided, can't verify
    if not signature:
        return None, False
        
    from sqlalchemy import select
    from app.models.organization import Organization
    
    # Get all active organizations
    query = select(Organization).where(Organization.is_active == True)
    result = await db.execute(query)
    organizations = list(result.scalars().all())
    
    # Try both production and testing URLs if they differ
    urls_to_try = [url]
    if settings.MAILCHIMP_WEBHOOK_BASE_URL_PRODUCTION != settings.MAILCHIMP_WEBHOOK_BASE_URL_TESTING:
        # If we're using the production URL, also try the testing URL as fallback
        production_url = f"{settings.MAILCHIMP_WEBHOOK_BASE_URL_PRODUCTION}{settings.WEBHOOK_PATH}"
        testing_url = f"{settings.MAILCHIMP_WEBHOOK_BASE_URL_TESTING}{settings.WEBHOOK_PATH}"
        
        # Add the other URL as a fallback
        if url == production_url:
            urls_to_try.append(testing_url)
        elif url == testing_url:
            urls_to_try.append(production_url)
    
    # Try to verify the signature for each organization
    for org in organizations:
        # Save the current webhook secret
        current_secret = self.webhook_secret
        
        try:
            # Use this organization's secret
            self.webhook_secret = org.mandrill_webhook_secret
            
            # Try each URL
            for try_url in urls_to_try:
                # Verify the signature
                if self.verify_signature(signature, try_url, body):
                    return org, True
        finally:
            # Restore the original secret
            self.webhook_secret = current_secret
    
    # No matching organization found
    return None, False
```

* **File**: `app/integrations/email/client.py`
* **Tests**: 
  * `app/tests/test_unit/test_integrations/test_email_client.py::test_identify_organization_by_signature`
  * `app/tests/test_unit/test_integrations/test_email_client.py::test_identify_organization_by_signature_with_multiple_environments`
* **Tracker Update**:
  * Set sub-task 2.2 status to `completed`
  * Set Step 2 status to `completed`
  * Update `current_step` to 3

## Step 3: Webhook Endpoint Updates

### Sub-task 3.1: Update receive_mandrill_webhook method

Update the webhook router to extract and verify signatures:

```python
@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    # ... existing code ...
)
async def receive_mandrill_webhook(
    request: Request,
    db: AsyncSession = get_db_session,
    email_service: EmailService = get_email_handler,
    client: WebhookClient = get_webhook,
) -> JSONResponse:
    """Handle Mandrill email webhook requests."""
    try:
        # Extract the signature from headers
        signature = request.headers.get("X-Mailchimp-Signature")
        
        # Prepare the webhook body
        body, error_response = await _prepare_webhook_body(request)
        
        # Return error response if parsing failed
        if error_response:
            return error_response
            
        # Verify we have a body to process
        if body is None:
            # ... existing code ...
        
        # Validate the webhook signature if provided and get organization
        organization = None
        is_verified = False
        
        if signature and hasattr(client, "identify_organization_by_signature"):
            # Get the appropriate webhook URL from settings
            webhook_url = settings.get_webhook_url
            
            # Identify organization by signature
            organization, is_verified = await client.identify_organization_by_signature(
                signature, webhook_url, body, db
            )
        
        # Store the organization with the request for use in services
        request.state.organization = organization
        request.state.is_verified = is_verified
        
        # Continue with existing code for handling the webhook
        # ... existing ping and empty event handling ...
        
        # Handle based on body type (list or dict)
        if isinstance(body, list):
            return await _handle_event_list(body, client, email_service, request)
        return await _handle_single_event_dict(body, client, email_service, request)
    except Exception as e:
        # ... existing exception handling ...
```

* **File**: `app/api/v1/endpoints/webhooks/mandrill/router.py`
* **Tests**: `app/tests/test_integration/test_api/test_webhooks.py::test_webhook_signature_validation`
* **Tracker Update**: Set sub-task 3.1 status to `completed`

### Sub-task 3.2: Add environment-aware logging

Add environment information to webhook logging:

```python
# After organization identification in receive_mandrill_webhook
if is_verified:
    logger.info(
        f"Verified webhook signature for organization: {organization.name} "
        f"in environment: {settings.API_ENV}"
    )
else:
    logger.warning(
        f"Received webhook with invalid or unknown signature "
        f"in environment: {settings.API_ENV}"
    )
```

* **File**: `app/api/v1/endpoints/webhooks/mandrill/router.py`
* **Tests**: N/A (logging enhancement)
* **Tracker Update**:
  * Set sub-task 3.2 status to `completed`
  * Set Step 3 status to `completed`
  * Update `current_step` to 4

## Step 4: Email Processing Service Updates

### Sub-task 4.1: Update _process_single_event method

Update to handle organization from request:

```python
async def _process_single_event(
    client: WebhookClient,
    email_service: EmailService,
    event: dict[str, Any],
    event_index: int,
    request: Request | None = None,
) -> bool:
    """Process a single Mandrill event."""
    try:
        # ... existing code ...
        
        # Get organization from request state if available
        organization = None
        if request and hasattr(request.state, "organization"):
            organization = request.state.organization
        
        # Process the webhook data with organization context
        webhook_data = await client.parse_webhook(formatted_event)
        await email_service.process_webhook(webhook_data, organization=organization)
        return True
    except Exception as event_err:
        # ... existing exception handling ...
```

* **File**: `app/api/v1/endpoints/webhooks/mandrill/processors.py`
* **Tests**: Covered by integration tests
* **Tracker Update**: Set sub-task 4.1 status to `completed`

### Sub-task 4.2: Update webhook handlers to pass request

Update handlers to pass the request object:

```python
async def _handle_event_list(
    body: list[dict[str, Any]],
    client: WebhookClient,
    email_service: EmailService,
    request: Request | None = None,
) -> JSONResponse:
    # ... existing code with updates to pass request ...
    for idx, event in enumerate(body):
        await _process_single_event(client, email_service, event, idx, request)
    # ... rest of existing code ...

async def _handle_single_event_dict(
    body: dict[str, Any],
    client: WebhookClient,
    email_service: EmailService,
    request: Request | None = None,
) -> JSONResponse:
    # ... existing code with updates to pass request ...
    await _process_single_event(client, email_service, body, 0, request)
    # ... rest of existing code ...
```

* **File**: `app/api/v1/endpoints/webhooks/mandrill/processors.py`
* **Tests**: Covered by integration tests
* **Tracker Update**: Set sub-task 4.2 status to `completed`

### Sub-task 4.3: Update process_webhook method

Update to use pre-identified organization:

```python
async def process_webhook(
    self, 
    webhook: MailchimpWebhook, 
    organization: Organization | None = None
) -> Email:
    """Process a webhook containing email data."""
    try:
        # If organization is not provided, try to identify it from the email
        if organization is None:
            organization = await self._identify_organization(webhook.data.to_email)
        
        # Create the email model
        email = await self.store_email(
            webhook.data, webhook.webhook_id, webhook.event, organization
        )
        
        # ... existing attachment processing code ...
        
        return email
    except Exception as e:
        # ... existing exception handling ...
```

* **File**: `app/services/email_processing_service.py`
* **Tests**: Covered by integration tests
* **Tracker Update**:
  * Set sub-task 4.3 status to `completed`
  * Set Step 4 status to `completed`
  * Update `current_step` to 5

## Step 5: Router Chain Updates

### Sub-task 5.1: Update router function calls

Update the router calls to pass request parameter:

```python
# In receive_mandrill_webhook function
# Handle based on body type (list or dict)
if isinstance(body, list):
    return await _handle_event_list(body, client, email_service, request)
return await _handle_single_event_dict(body, client, email_service, request)
```

* **File**: `app/api/v1/endpoints/webhooks/mandrill/router.py`
* **Tests**: Covered by integration tests
* **Tracker Update**:
  * Set sub-task 5.1 status to `completed`
  * Set Step 5 status to `completed`
  * Update `current_step` to 6

## Step 6: Error Handling for Signature Verification

### Sub-task 6.1: Add environment-aware rejection settings

This was already implemented in Step 1, but ensure it's properly used:

```python
# Verify property exists in Settings class
@property
def should_reject_unverified(self) -> bool:
    """Determine if unverified webhooks should be rejected based on environment."""
    if self.API_ENV in ("production", "staging"):
        return self.MAILCHIMP_REJECT_UNVERIFIED_PRODUCTION
    return self.MAILCHIMP_REJECT_UNVERIFIED_TESTING
```

* **File**: `app/core/config.py`
* **Tests**: `app/tests/test_unit/test_core/test_config.py::test_should_reject_unverified_property`
* **Tracker Update**: Set sub-task 6.1 status to `completed`

### Sub-task 6.2: Update webhook router with rejection

Add rejection logic to webhook router:

```python
# After signature verification in receive_mandrill_webhook
if settings.should_reject_unverified and signature and not is_verified:
    logger.warning(
        f"Rejecting unverified webhook due to configuration in environment: {settings.API_ENV}"
    )
    return JSONResponse(
        content={
            "status": "error",
            "message": "Invalid webhook signature",
        },
        # Return 401 to cause Mailchimp to retry
        status_code=status.HTTP_401_UNAUTHORIZED,
    )
```

* **File**: `app/api/v1/endpoints/webhooks/mandrill/router.py`
* **Tests**: `app/tests/test_integration/test_api/test_webhooks.py::test_webhook_signature_validation_rejection`
* **Tracker Update**:
  * Set sub-task 6.2 status to `completed`
  * Set Step 6 status to `completed`
  * Update `current_step` to 7 (all steps completed)

## Testing Plan

After completing all implementation steps:

1. **Unit Tests**: Run unit tests to verify individual components
2. **Integration Tests**: Run integration tests to verify component interaction
3. **End-to-End Tests**: Run E2E tests to verify overall functionality

## Documentation Updates

Once implementation is complete:

1. Update API documentation to explain signature verification
2. Document the environment variables and configuration options
3. Add examples for webhook configuration in different environments

## Final Verification

Before marking as complete:

1. Run all tests: `python -m pytest`
2. Check code quality: `black . && isort . && flake8 && mypy app`
3. Update tracker status to mark project as complete 