#!/usr/bin/env python3
"""
Test script for sending a webhook to the Kave app on Heroku.
This simulates a MailChimp webhook with a test email containing an attachment.
"""

import argparse
import base64
import hashlib
import hmac
import json
import time

import requests


def get_webhook_signature(payload_str, secret):
    """Calculate the HMAC signature for the webhook."""
    signature = hmac.new(
        key=secret.encode(), msg=payload_str.encode(), digestmod=hashlib.sha256
    ).hexdigest()
    return signature


def create_test_payload():
    """Create a test email payload with an attachment."""
    return {
        "webhook_id": f"wh_test_{int(time.time())}",
        "event": "inbound_email",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "data": {
            "message_id": f"test-{int(time.time())}@example.com",
            "from_email": "test@example.com",
            "from_name": "Test Sender",
            "to_email": "recipient@example.com",
            "subject": "Test Email for Heroku Deployment",
            "body_plain": "Test email with attachment for Heroku deployment",
            "body_html": "<p>Test email with attachment for Heroku deployment</p>",
            "headers": {"Message-ID": f"test-{int(time.time())}@example.com"},
            "attachments": [
                {
                    "name": "test.txt",
                    "type": "text/plain",
                    "content": base64.b64encode(
                        b"This is a test attachment for Heroku deployment"
                    ).decode(),
                }
            ],
        },
    }


def send_webhook(url, payload, secret):
    """Send the webhook request with proper signature."""
    payload_str = json.dumps(payload)
    signature = get_webhook_signature(payload_str, secret)

    headers = {"Content-Type": "application/json", "X-Mailchimp-Signature": signature}

    print(f"Sending test webhook to {url}")
    response = requests.post(url, headers=headers, data=payload_str)
    return response


def main():
    parser = argparse.ArgumentParser(description="Test webhook sender for Kave app")
    parser.add_argument(
        "--url",
        default="https://kave-v2-a373f2753df6.herokuapp.com/webhooks/mailchimp",
        help="The webhook URL (default: Kave v2 Heroku app)",
    )
    parser.add_argument(
        "--secret",
        required=True,
        help="The webhook secret (MAILCHIMP_WEBHOOK_SECRET from Heroku config)",
    )

    args = parser.parse_args()

    payload = create_test_payload()
    response = send_webhook(args.url, payload, args.secret)

    print(f"Response status: {response.status_code}")
    print(f"Response body: {response.text}")

    # If successful, print commands to verify data was saved
    if response.status_code in (200, 202):
        print("\nWaiting for processing...")
        time.sleep(2)

        print("\nTo check if the email was saved in the database, run:")
        print(
            'heroku pg:psql -a kave-v2 -c "SELECT id, subject, from_email '
            "FROM emails WHERE subject='Test Email for Heroku Deployment';\""
        )

        print("\nTo check if the attachment was saved, run:")
        print(
            'heroku pg:psql -a kave-v2 -c "SELECT id, filename, storage_uri '
            "FROM attachments WHERE filename='test.txt';\""
        )

        # This requires real AWS credentials to be set
        print("\nTo check if the attachment was saved in S3, run:")
        print(
            'heroku run "aws s3 ls s3://YOUR_S3_BUCKET_NAME --recursive | '
            'grep test.txt" -a kave-v2'
        )


if __name__ == "__main__":
    main()
