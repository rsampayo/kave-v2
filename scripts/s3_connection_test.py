#!/usr/bin/env python3
"""
S3 Connection Test Script

This script verifies that the S3 configuration is working properly.
It attempts to create a test file in the S3 bucket and then deletes it.
Use this before deploying to Heroku to ensure your S3 credentials are valid.
"""

import asyncio
import logging
import sys
from datetime import datetime

import aioboto3
from botocore.exceptions import ClientError

# Import settings from the app to use the same environment variables
from app.core.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def test_s3_connection() -> bool:
    """Test the S3 connection using the configured settings.

    Returns:
        bool: True if the connection is successful, False otherwise
    """
    if not settings.USE_S3_STORAGE:
        logger.warning("S3 storage is not enabled (USE_S3_STORAGE=False)")
        return False

    if not settings.S3_BUCKET_NAME:
        logger.error("S3 bucket name is not configured (S3_BUCKET_NAME is empty)")
        return False

    if not settings.AWS_ACCESS_KEY_ID or not settings.AWS_SECRET_ACCESS_KEY:
        logger.error("AWS credentials are not configured")
        return False

    try:
        logger.info(f"Testing S3 connection to bucket: {settings.S3_BUCKET_NAME}")

        # Create a unique test object key
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        test_key = f"test/s3_connection_test_{timestamp}.txt"
        test_content = f"S3 connection test at {datetime.now().isoformat()}"

        # Initialize S3 session
        session = aioboto3.Session(
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
        )

        # Try to upload a test file
        logger.info(f"Uploading test file to s3://{settings.S3_BUCKET_NAME}/{test_key}")
        async with session.client("s3") as s3:
            # Upload test file
            await s3.put_object(
                Bucket=settings.S3_BUCKET_NAME,
                Key=test_key,
                Body=test_content.encode("utf-8"),
                ContentType="text/plain",
            )
            logger.info("Test file uploaded successfully")

            # Verify we can retrieve it
            logger.info("Retrieving test file")
            response = await s3.get_object(
                Bucket=settings.S3_BUCKET_NAME,
                Key=test_key,
            )

            async with response["Body"] as stream:
                content = await stream.read()
                content_str = content.decode("utf-8")
                logger.info(f"Retrieved content: {content_str}")
                assert content_str == test_content, "Content mismatch"

            # Clean up
            logger.info("Deleting test file")
            await s3.delete_object(
                Bucket=settings.S3_BUCKET_NAME,
                Key=test_key,
            )
            logger.info("Test file deleted successfully")

        logger.info("✅ S3 connection test passed!")
        return True

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_message = e.response.get("Error", {}).get("Message", str(e))
        logger.error(f"S3 connection failed: {error_code} - {error_message}")
        logger.error("Please check your AWS credentials and bucket configuration")
        return False
    except Exception as e:
        logger.error(f"Unexpected error during S3 connection test: {str(e)}")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_s3_connection())
    if not success:
        sys.exit(1)  # Exit with error code
    sys.exit(0)  # Exit with success code
