#!/usr/bin/env python3
"""
Debugging script for Mandrill webhooks.
Saves raw webhook data to a file for analysis.
"""

import json
import logging
import time

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("webhook_debug.log"), logging.StreamHandler()],
)
logger = logging.getLogger("webhook_debugger")

app = FastAPI()


@app.post("/debug")
async def debug_webhook(request: Request):
    """Receive and log webhook for debugging."""
    try:
        # Log headers
        headers = dict(request.headers)
        logger.info(f"Request headers: {json.dumps(headers, indent=2)}")

        # Get the signature
        signature = headers.get("x-mandrill-signature")
        logger.info(f"Signature: {signature}")

        # Get raw body
        raw_body = await request.body()
        logger.info(f"Raw body: {raw_body}")

        # Try to parse as JSON
        try:
            body = json.loads(raw_body)
            logger.info(f"JSON body: {json.dumps(body, indent=2)}")
        except Exception:
            logger.info("Body is not valid JSON")

        # Save to file for later analysis
        timestamp = int(time.time())
        with open(f"webhook_dump_{timestamp}.json", "w") as f:
            f.write(
                json.dumps(
                    {
                        "headers": headers,
                        "signature": signature,
                        "body": raw_body.decode("utf-8", errors="replace"),
                    },
                    indent=2,
                )
            )

        return JSONResponse(
            content={"status": "success", "message": "Webhook data logged"},
            status_code=200,
        )
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}", exc_info=True)
        return JSONResponse(
            content={"status": "error", "message": str(e)},
            status_code=200,  # Return 200 to avoid retries
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
