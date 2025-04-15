# Implementation Plan for Mailchimp Webhook Signature Verification

## 1. Overview

This plan outlines the implementation of Mailchimp webhook signature verification in the Kave application to:

1. Verify webhook authenticity using HMAC-SHA1 signatures
2. Identify the organization sending the webhook based on the signature
3. Link incoming emails to the correct organization

## 2. Current Architecture Analysis

### 2.1 Organization Model
- `Organization` model already exists with:
  - `id`, `name`, `webhook_email`, `mandrill_api_key`, `mandrill_webhook_secret`, `is_active`
  - Relationship with `Email` model (`emails`)

### 2.2 Email Processing Flow
1. Webhook request arrives at `/v1/webhooks/mandrill` endpoint
2. Request body is parsed and extracted
3. `WebhookClient` validates and parses the webhook data
4. `EmailProcessingService` processes the webhook and creates an `Email` record
5. Organization is currently identified by the recipient email (`to_email`)

### 2.3 Gaps in Current Implementation
1. No webhook signature verification exists
2. `WebhookClient` has a `webhook_secret` property but doesn't use it for verification
3. Webhook URL is not stored in the configuration
4. Emails are linked to organizations based on recipient email, not signature
5. No separate URLs for production and testing environments

## 3. Implementation Tasks

### 3.1 Environment Configuration Updates

1. Add webhook URLs and related configuration to `.env` file for both production and testing:
   ```
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

2. Update `Settings` class in `app/core/config.py` to use these environment variables:
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

3. Remove hardcoded URLs from the webhook client and Organization model updates:
   ```python
   # Update Organization model without hardcoded URLs
   production_webhook_key: Mapped[str | None] = mapped_column(
       String(255), nullable=True, 
       comment="Identifier for the production webhook in Mailchimp"
   )
   testing_webhook_key: Mapped[str | None] = mapped_column(
       String(255), nullable=True, 
       comment="Identifier for the testing webhook in Mailchimp"
   )
   ```

4. Update the README.md to include a `.env.example` with these environment variables and explanations.

### 3.2 WebhookClient Enhancements

1. Create a signature verification method in `app/integrations/email/client.py`:
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
           # This is a simplification - Mailchimp might handle this differently
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

2. Add a method to identify organization by signature with environment support:
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

### 3.3 Webhook Endpoint Updates

1. Modify the webhook router to extract and verify signatures in `app/api/v1/endpoints/webhooks/mandrill/router.py`:
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
       """Handle Mandrill email webhook requests.
       
       # ... existing docstring ...
       """
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
               
               # Log verification result with environment information
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
           
           # Store the organization with the request for use in services
           request.state.organization = organization
           request.state.is_verified = is_verified
           
           # Continue with existing code for handling the webhook
           # ... existing ping and empty event handling ...
           
           # Handle based on body type (list or dict)
           if isinstance(body, list):
               return await _handle_event_list(body, client, email_service)
           return await _handle_single_event_dict(body, client, email_service)
       except Exception as e:
           # ... existing exception handling ...
   ```

### 3.4 Email Processing Service Updates

1. Modify `_process_single_event` in `app/api/v1/endpoints/webhooks/mandrill/processors.py`:
   ```python
   async def _process_single_event(
       client: WebhookClient,
       email_service: EmailService,
       event: dict[str, Any],
       event_index: int,
       request: Request | None = None,
   ) -> bool:
       """Process a single Mandrill event.
       
       # ... existing docstring ...
       
       Args:
           # ... existing args ...
           request: Optional FastAPI request object containing state
       """
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

2. Update the webhook handlers to pass the request:
   ```python
   async def _handle_event_list(
       body: list[dict[str, Any]],
       client: WebhookClient,
       email_service: EmailService,
       request: Request | None = None,
   ) -> JSONResponse:
       # ... existing code with minor updates to pass request ...
   
   async def _handle_single_event_dict(
       body: dict[str, Any],
       client: WebhookClient,
       email_service: EmailService,
       request: Request | None = None,
   ) -> JSONResponse:
       # ... existing code with updates to pass request ...
   ```

3. Modify the `process_webhook` method in `app/services/email_processing_service.py`:
   ```python
   async def process_webhook(
       self, 
       webhook: MailchimpWebhook, 
       organization: Organization | None = None
   ) -> Email:
       """Process a webhook containing email data.
       
       Args:
           webhook: The MailChimp webhook data
           organization: Optional pre-identified organization from signature
           
       Returns:
           Email: The created email model
           
       Raises:
           ValueError: If email processing fails
       """
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

### 3.5 Router Chain Updates

1. Update the main router function in `app/api/v1/endpoints/webhooks/mandrill/router.py`:
   ```python
   # ... in receive_mandrill_webhook function ...
   
   # Handle based on body type (list or dict)
   if isinstance(body, list):
       return await _handle_event_list(body, client, email_service, request)
   return await _handle_single_event_dict(body, client, email_service, request)
   ```

### 3.6 Error Handling for Failed Signature Verification

1. Add option to reject unverified webhooks in `app/core/config.py` with environment awareness:
   ```python
   # In Settings class
   MAILCHIMP_REJECT_UNVERIFIED_PRODUCTION: bool = False
   MAILCHIMP_REJECT_UNVERIFIED_TESTING: bool = False
   
   @property
   def should_reject_unverified(self) -> bool:
       """Determine if unverified webhooks should be rejected based on environment.
       
       Returns:
           bool: True if unverified webhooks should be rejected in the current environment
       """
       if self.API_ENV in ("production", "staging"):
           return self.MAILCHIMP_REJECT_UNVERIFIED_PRODUCTION
       return self.MAILCHIMP_REJECT_UNVERIFIED_TESTING
   ```

2. Update the webhook router to check this setting:
   ```python
   # After signature verification
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

### 3.7 Organization Configuration for Multiple Environments

1. Update the `Organization` model to support multiple webhook configurations:
   ```python
   # Update Organization model
   production_webhook_url: Mapped[str | None] = mapped_column(
       String(255), nullable=True, 
       comment="Production webhook URL registered with Mailchimp"
   )
   testing_webhook_url: Mapped[str | None] = mapped_column(
       String(255), nullable=True, 
       comment="Testing webhook URL registered with Mailchimp"
   )
   ```

2. Update Organization schemas to include URL fields:
   ```python
   # In OrganizationCreate and OrganizationUpdate schemas
   production_webhook_url: str | None = Field(
       None, description="Production webhook URL registered with Mailchimp"
   )
   testing_webhook_url: str | None = Field(
       None, description="Testing webhook URL registered with Mailchimp"
   )
   ```

## 4. Testing Plan

### 4.1 Unit Tests

1. Create tests for signature verification in `app/tests/test_unit/test_integrations/test_email_client.py`:
   ```python
   @pytest.mark.asyncio
   async def test_verify_signature_valid():
       """Test signature verification with a valid signature."""
       
   @pytest.mark.asyncio
   async def test_verify_signature_invalid():
       """Test signature verification with an invalid signature."""
       
   @pytest.mark.asyncio
   async def test_identify_organization_by_signature():
       """Test organization identification by signature."""
       
   @pytest.mark.asyncio
   async def test_identify_organization_by_signature_with_multiple_environments():
       """Test organization identification by signature with different environment URLs."""
   ```

### 4.2 Integration Tests

1. Update existing webhook tests in `app/tests/test_integration/test_api/test_webhooks.py`:
   ```python
   @pytest.mark.asyncio
   async def test_webhook_signature_validation():
       """Test webhook processing with signature validation."""
       
   @pytest.mark.asyncio
   async def test_webhook_signature_validation_different_environments():
       """Test webhook processing with signature validation in different environments."""
   ```

### 4.3 End-to-End Tests

1. Create end-to-end tests in `app/tests/test_e2e/test_webhook_flow.py`:
   ```python
   @pytest.mark.asyncio
   async def test_webhook_e2e_with_signature_verification():
       """Test the full webhook processing flow with signature verification."""
       
   @pytest.mark.asyncio
   async def test_webhook_e2e_with_environment_specific_urls():
       """Test the webhook flow with environment-specific URLs."""
   ```

### 4.4 Manual Testing

1. Create a test script to send webhooks with valid and invalid signatures for both environments:
   ```python
   # Add to test_webhook.py
   
   def send_production_webhook(url, payload, secret):
       """Send a webhook to the production environment."""
       # Use production URL for signature generation
       ...
   
   def send_testing_webhook(url, payload, secret):
       """Send a webhook to the testing environment."""
       # Use testing URL for signature generation
       ...
   ```

## 5. Documentation

1. Update API documentation to explain signature verification
2. Document the environment variables and configuration options for different environments
3. Add examples for creating organizations with webhook secrets
4. Document how to configure Mailchimp webhooks for different environments:
   - Production webhook configuration
   - Testing/Development webhook configuration
   - How to maintain separate webhook secrets

## 6. Migration Plan

1. Deploy the changes to a staging environment
2. Test with real Mailchimp webhooks using different URLs for testing and production
3. Monitor error rates and performance
4. Gradually enable signature verification in production by:
   - Setting `MAILCHIMP_REJECT_UNVERIFIED_TESTING=True` first
   - Creating organizations with proper webhook secrets for both environments
   - Testing verification in the testing environment
   - Setting `MAILCHIMP_REJECT_UNVERIFIED_PRODUCTION=False` initially
   - Testing verification without rejection in production
   - Finally enabling `MAILCHIMP_REJECT_UNVERIFIED_PRODUCTION=True` when confident

## 7. Webhook Setup Instructions for Organizations

### 7.1 Production Environment

1. Create a webhook in Mailchimp Transactional pointing to:
   `https://api.example.com/v1/webhooks/mandrill`
2. Save the generated webhook secret
3. Add to your organization in the Kave application:
   - Production webhook URL
   - Webhook secret
   - Set organization as active

### 7.2 Testing/Development Environment

1. Create a separate webhook in Mailchimp Transactional pointing to:
   `https://dev.example.com/v1/webhooks/mandrill` or
   `https://your-ngrok-url.ngrok.io/v1/webhooks/mandrill`
2. Save the generated webhook secret (different from production)
3. Update your organization in the Kave application:
   - Testing webhook URL
   - Testing webhook secret
