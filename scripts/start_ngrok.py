#!/usr/bin/env python3
"""
Ngrok tunnel management script for local webhook testing.

This script starts an ngrok tunnel to expose your local FastAPI server to the internet,
making it accessible for services like Mandrill to send webhook events.
"""

import asyncio
import logging
import sys
from typing import Any, Dict, Optional

import httpx
from pydantic_settings import BaseSettings

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class NgrokSettings(BaseSettings):
    """Ngrok configuration settings."""

    NGROK_AUTH_TOKEN: Optional[str] = None
    NGROK_API_KEY: Optional[str] = None
    NGROK_REGION: str = "us"
    NGROK_LOCAL_PORT: int = 8000
    WEBHOOK_PATH: str = "/v1/webhooks/mandrill"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore",  # Ignore extra fields in .env
    }


class NgrokTunnel:
    """Manages an ngrok tunnel for local webhook testing."""

    def __init__(self, settings: NgrokSettings):
        """Initialize with settings."""
        self.settings = settings
        self.tunnel_url: Optional[str] = None
        self.webhook_url: Optional[str] = None
        self.process: Optional[asyncio.subprocess.Process] = None

    async def check_existing_tunnel(self) -> Optional[Dict[str, str]]:
        """Check if ngrok is already running and get tunnel info."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get("http://localhost:4040/api/tunnels")
                if response.status_code == 200:
                    data = response.json()
                    for tunnel in data.get("tunnels", []):
                        if tunnel.get("proto") == "https":
                            self.tunnel_url = tunnel["public_url"]
                            self.webhook_url = (
                                f"{self.tunnel_url}{self.settings.WEBHOOK_PATH}"
                            )
                            logger.info(
                                f"Found existing ngrok tunnel: {self.tunnel_url}"
                            )
                            return {
                                "tunnel_url": self.tunnel_url,
                                "webhook_url": self.webhook_url,
                            }
        except Exception as e:
            logger.info(f"No existing ngrok tunnel found: {e}")

        return None

    async def start_ngrok_process(self) -> None:
        """Start ngrok as a subprocess."""
        cmd = [
            "ngrok",
            "http",
            str(self.settings.NGROK_LOCAL_PORT),
            "--region",
            self.settings.NGROK_REGION,
        ]

        if self.settings.NGROK_AUTH_TOKEN:
            cmd.extend(["--authtoken", self.settings.NGROK_AUTH_TOKEN])

        logger.info(f"Starting ngrok with command: {' '.join(cmd)}")
        self.process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # Give ngrok time to start up
        await asyncio.sleep(3)

    async def get_tunnel_info(self) -> Dict[str, str]:
        """Get tunnel URL from ngrok API."""
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:4040/api/tunnels")
            if response.status_code != 200:
                raise RuntimeError(f"Failed to get ngrok tunnels: {response.text}")

            data = response.json()
            for tunnel in data.get("tunnels", []):
                if tunnel.get("proto") == "https":
                    self.tunnel_url = tunnel["public_url"]
                    self.webhook_url = f"{self.tunnel_url}{self.settings.WEBHOOK_PATH}"
                    break

            if not self.tunnel_url:
                raise RuntimeError("No HTTPS ngrok tunnel found")

            logger.info(f"Ngrok tunnel started: {self.tunnel_url}")
            logger.info(f"Webhook URL: {self.webhook_url}")

            return {
                "tunnel_url": self.tunnel_url,
                "webhook_url": self.webhook_url,
            }

    async def start(self) -> Dict[str, Any]:
        """Start the ngrok tunnel and return tunnel information."""
        try:
            # Check for existing tunnel
            existing_tunnel = await self.check_existing_tunnel()
            if existing_tunnel:
                return existing_tunnel

            # Start a new tunnel
            await self.start_ngrok_process()

            # Get tunnel information
            return await self.get_tunnel_info()

        except Exception as e:
            logger.error(f"Error starting ngrok: {e}")
            if self.process:
                self.process.terminate()
            raise

    async def stop(self) -> None:
        """Stop the ngrok tunnel."""
        if self.process:
            self.process.terminate()
            try:
                await self.process.wait()
            except ProcessLookupError:
                pass
            logger.info("Ngrok tunnel stopped")


async def main() -> None:
    """Run the ngrok tunnel manager."""
    settings = NgrokSettings()
    tunnel = NgrokTunnel(settings)

    try:
        tunnel_info = await tunnel.start()

        print("\n===== NGROK TUNNEL INFORMATION =====")
        print(f"Base URL: {tunnel_info['tunnel_url']}")
        print(f"Webhook URL: {tunnel_info['webhook_url']}")
        print("\nUse this URL in your Mandrill webhook configuration.")
        print("Press Ctrl+C to stop the tunnel...")

        # Keep the script running until user interrupts
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down ngrok tunnel...")
    finally:
        await tunnel.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutting down...")
        sys.exit(0)
