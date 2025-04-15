#!/usr/bin/env python3
"""
Start FastAPI app with ngrok for webhook testing.

This script starts both the FastAPI application and an ngrok tunnel to expose
the local server to the internet, making it accessible for webhook testing with
services like Mandrill.
"""

import asyncio
import logging
import signal
import sys
from typing import Optional

from scripts.start_ngrok import NgrokSettings, NgrokTunnel

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class AppRunner:
    """Manages the FastAPI application."""

    def __init__(self, port: int = 8000):
        """Initialize with port."""
        self.port = port
        self.process: Optional[asyncio.subprocess.Process] = None

    async def start(self) -> None:
        """Start the FastAPI application with uvicorn."""
        try:
            cmd = [
                "uvicorn",
                "app.main:app",
                "--host",
                "0.0.0.0",
                "--port",
                str(self.port),
                "--reload",
            ]

            logger.info(f"Starting FastAPI app with command: {' '.join(cmd)}")

            self.process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # Start background task to log stdout and stderr
            asyncio.create_task(self._log_output())

            logger.info(f"FastAPI app started on port {self.port}")
        except Exception as e:
            logger.error(f"Error starting FastAPI app: {e}")
            raise

    async def _log_output(self) -> None:
        """Log stdout and stderr from the process."""
        if not self.process:
            return

        while True:
            if self.process.stdout:
                line = await self.process.stdout.readline()
                if line:
                    logger.info(f"UVICORN: {line.decode().strip()}")
                else:
                    break
            else:
                break

    async def stop(self) -> None:
        """Stop the FastAPI application."""
        if self.process:
            self.process.send_signal(signal.SIGINT)
            try:
                await self.process.wait()
            except ProcessLookupError:
                pass
            logger.info("FastAPI app stopped")


async def main() -> None:
    """Run the FastAPI app and ngrok tunnel."""
    settings = NgrokSettings()
    app_runner = AppRunner(port=settings.NGROK_LOCAL_PORT)
    tunnel = NgrokTunnel(settings)

    try:
        # Start the FastAPI app
        await app_runner.start()

        # Give the app time to start up
        await asyncio.sleep(2)

        # Start the ngrok tunnel
        tunnel_info = await tunnel.start()

        print("\n===== DEVELOPMENT ENVIRONMENT =====")
        print(f"FastAPI app running at: http://localhost:{settings.NGROK_LOCAL_PORT}")
        print(f"Ngrok tunnel: {tunnel_info['tunnel_url']}")
        print(f"Webhook URL for Mandrill: {tunnel_info['webhook_url']}")
        print("\nUse this webhook URL in your Mandrill configuration.")
        print("Press Ctrl+C to stop all services...\n")

        # Keep the script running until user interrupts
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down services...")
    finally:
        # Stop services in reverse order
        await tunnel.stop()
        await app_runner.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutting down...")
        sys.exit(0)
