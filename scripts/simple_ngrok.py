#!/usr/bin/env python3
"""
Simple script to start ngrok and print the webhook URL.

This script:
1. Starts ngrok using subprocess
2. Waits for ngrok to start
3. Gets the public URL from the ngrok API
4. Prints the webhook URL for Mandrill
"""

import json
import subprocess
import sys
import time
import urllib.request

# Configuration
NGROK_PORT = 8000
WEBHOOK_PATH = "/v1/webhooks/mandrill"


def get_ngrok_url():
    """Get the ngrok public URL by calling its local API."""
    time.sleep(2)  # Give ngrok time to start
    try:
        response = urllib.request.urlopen("http://localhost:4040/api/tunnels")
        data = json.loads(response.read().decode())

        for tunnel in data.get("tunnels", []):
            if tunnel.get("proto") == "https":
                return tunnel["public_url"]

        return None
    except Exception as e:
        print(f"Error getting ngrok URL: {e}")
        return None


def main():
    """Start ngrok and print the webhook URL."""
    # Check if ngrok is already running
    try:
        urllib.request.urlopen("http://localhost:4040")
        print("ngrok is already running. Using existing tunnel.")
    except urllib.error.URLError:
        # Start ngrok in the background
        print("Starting ngrok...")
        subprocess.Popen(
            ["ngrok", "http", str(NGROK_PORT)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    # Get the ngrok URL
    ngrok_url = get_ngrok_url()

    if not ngrok_url:
        print("Failed to get ngrok URL. Make sure ngrok is running.")
        sys.exit(1)

    webhook_url = f"{ngrok_url}{WEBHOOK_PATH}"

    print("\n===== NGROK TUNNEL INFORMATION =====")
    print(f"Base URL: {ngrok_url}")
    print(f"Webhook URL for Mandrill: {webhook_url}")
    print("\nUse this webhook URL in your Mandrill configuration:")
    print(webhook_url)
    print("\nNgrok web interface: http://localhost:4040")
    print("\nPress Ctrl+C to exit this script, but ngrok will continue running.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nExiting script. Ngrok is still running in the background.")


if __name__ == "__main__":
    main()
