# Webhook Signature Verification Debugging Guide

This guide explains how to monitor, test, and debug the Mailchimp webhook signature verification system.

## Monitoring Signature Verification

The signature verification process has been enhanced with detailed logging. Here's what to look for:

### Log Levels

- **INFO**: Normal operation, successful verification
- **WARNING**: Potential issues (invalid signatures, missing secrets)
- **DEBUG**: Detailed information for troubleshooting
- **ERROR**: Verification failures and exceptions

### Key Log Messages

Look for these signature-specific log messages:

- `🔑 SIGNATURE` markers for all signature-related logs
- `✅ Verified webhook signature` for successful verification
- `❌ Received webhook with invalid or unknown signature` for failed verification
- `🛑 Rejecting unverified webhook` when rejecting unverified webhooks

### Critical Values to Check

When troubleshooting, verify these in the logs:

1. The webhook URL being used for verification
2. The webhook environment (testing vs. production)
3. The calculated signature vs. received signature
4. Which organization's secret was used for verification

## Testing Signature Verification

### Using the Test Script

We've provided a test script to help verify signatures are working correctly:

```bash
# Test all organizations
./test_signature.py

# Test a specific organization
./test_signature.py --org 1
```

The script will:
1. List all active organizations
2. Generate valid signatures using their webhook secrets
3. Verify the signatures with the WebhookClient
4. Provide cURL commands for manual testing

### Manual Testing

Use the generated cURL commands from the test script to manually send test webhooks with valid signatures:

```bash
curl -X POST "https://your-webhook-url/v1/webhooks/mandrill" \
  -H "Content-Type: application/json" \
  -H "X-Mailchimp-Signature: YourGeneratedSignature" \
  -d "{\"webhook_data\": \"here\"}"
```

## Common Issues and Solutions

### Invalid Signatures

If signatures are consistently invalid, check:

1. **Webhook URL mismatch**: Ensure the URL registered in Mailchimp exactly matches what's in your settings
2. **Secret mismatch**: Verify the webhook secret in the organization record matches what's configured in Mailchimp
3. **URL processing**: Check if your reverse proxy or load balancer is modifying the URL path

### Environment Configuration

Verify your environment variables are set correctly:

```
MAILCHIMP_WEBHOOK_BASE_URL_PRODUCTION=https://api.example.com
MAILCHIMP_WEBHOOK_BASE_URL_TESTING=https://dev.example.com
WEBHOOK_PATH=/v1/webhooks/mandrill
MAILCHIMP_REJECT_UNVERIFIED_PRODUCTION=false
MAILCHIMP_REJECT_UNVERIFIED_TESTING=false
MAILCHIMP_WEBHOOK_ENVIRONMENT=testing
```

### Debugging with Increased Logging

To see more detailed logs during troubleshooting:

1. Set the logger level to DEBUG in `app/main.py`:
   ```python
   logging.basicConfig(level=logging.DEBUG)
   ```

2. Or use environment variables to control log levels:
   ```
   export LOG_LEVEL=DEBUG
   ```

3. Look for signature verification details in the logs:
   ```
   grep "SIGNATURE\|verify_signature\|identify_organization" app.log
   ```

## Configuring Mailchimp

1. In Mailchimp/Mandrill, set your webhook URL to match your `MAILCHIMP_WEBHOOK_BASE_URL_*` setting
2. Generate a secure webhook signing secret (32+ characters) and save it in both:
   - Mailchimp/Mandrill webhook configuration
   - Your organization's `mandrill_webhook_secret` field

## Additional Monitoring

For critical webhook processing, set up alerts for:

1. Consistently failing signature verification
2. Rejections of webhooks due to invalid signatures
3. Unexpected changes in webhook URL patterns 