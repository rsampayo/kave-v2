import hashlib
import hmac
import json
import os

import requests

# Load webhook secret from .env file
webhook_secret = os.getenv("MAILCHIMP_WEBHOOK_SECRET", "test_webhook_secret")

# Path to the webhook data file
webhook_file = "app/tests/test_data/mock_webhook_with_attachment.json"

# URL of the endpoint to test
endpoint = "http://localhost:8000/webhooks/mailchimp"

# Read the webhook data
with open(webhook_file, "r") as f:
    webhook_data = json.load(f)

# Convert webhook data to JSON bytes
webhook_json = json.dumps(webhook_data).encode()

# Calculate the signature using HMAC-SHA256
signature = hmac.new(
    key=webhook_secret.encode(), msg=webhook_json, digestmod=hashlib.sha256
).hexdigest()

print(f"Generated signature: {signature}")

# Send the webhook request with the signature in the headers
response = requests.post(
    endpoint,
    data=webhook_json,
    headers={"Content-Type": "application/json", "X-Mailchimp-Signature": signature},
)

print(f"Status code: {response.status_code}")
print(f"Response: {response.text}")
