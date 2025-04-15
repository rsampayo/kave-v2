#!/usr/bin/env python3
"""
Test script for sending a webhook in Mandrill's actual format.
This simulates the actual webhook format Mandrill uses.
"""

import argparse
import base64
import hashlib
import hmac
import json
import time

import requests


def get_webhook_signature(url, payload_str, secret):
    """Calculate the HMAC signature for the webhook.

    Mandrill uses the URL + raw POST body for signature calculation.
    """
    # Combine URL and payload for signing
    signed_data = url + payload_str

    # Create HMAC-SHA1 signature and base64 encode
    signature = base64.b64encode(
        hmac.new(
            key=secret.encode("utf-8"),
            msg=signed_data.encode("utf-8"),
            digestmod=hashlib.sha1,
        ).digest()
    ).decode("utf-8")

    return signature


def create_mandrill_payload():
    """Create a payload in Mandrill's format.

    Based on actual Mandrill webhooks in production.
    """
    timestamp = int(time.time())

    # Create a webhook in the format Mandrill actually uses
    return [
        {
            "event": "inbound",
            "ts": timestamp,
            "msg": {
                "_id": f"message-id-{timestamp}",
                "sender": "test@example.com",
                "email": "test@example.com",
                "subject": "Test Mandrill Format Email",
                "from_email": "test@example.com",
                "from_name": "Test Sender",
                "to": [["recipient@example.com", "Recipient Name"]],
                "text": "This is a test email in Mandrill's format",
                "html": "<p>This is a test email in Mandrill's format</p>",
                "spam_report": {"score": 0.5, "matched_rules": []},
                "attachments": {
                    "test.txt": {
                        "name": "test.txt",
                        "type": "text/plain",
                        "content": base64.b64encode(
                            b"Test attachment content"
                        ).decode(),
                    }
                },
                "headers": {"Message-Id": f"<message-{timestamp}@example.com>"},
            },
        }
    ]


def send_webhook(url, payload, secret):
    """Send the webhook request with proper signature."""
    # Convert to JSON string
    payload_str = json.dumps(payload)

    # Generate signature using URL + payload
    signature = get_webhook_signature(url, payload_str, secret)

    print(f"URL for signature: {url}")
    print(f"Generated signature: {signature}")

    # Set headers with signature
    headers = {"Content-Type": "application/json", "X-Mandrill-Signature": signature}

    print(f"Sending test webhook to {url}")
    print(f"Headers: {headers}")
    print(f"Payload first 100 chars: {payload_str[:100]}...")

    # Send the request
    response = requests.post(url, headers=headers, data=payload_str)
    return response


def main():
    parser = argparse.ArgumentParser(description="Test Mandrill webhook sender")
    parser.add_argument(
        "--url",
        default="https://f0e5-66-68-240-65.ngrok-free.app/v1/webhooks/mandrill",
        help="The webhook URL (default: Ngrok webhook URL)",
    )
    parser.add_argument("--secret", required=True, help="The webhook secret")

    args = parser.parse_args()

    payload = create_mandrill_payload()
    response = send_webhook(args.url, payload, args.secret)

    print(f"Response status: {response.status_code}")
    print(f"Response body: {response.text}")


if __name__ == "__main__":
    main()
