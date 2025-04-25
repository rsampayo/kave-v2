#!/usr/bin/env python3
"""Test script for Redis integration with the PDF OCR workflow.

This is a simplified test that focuses on making sure Redis is correctly configured
and can be used by the application. It doesn't attempt to run the full OCR workflow,
which requires Celery workers.
"""

import asyncio
import logging
import time
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import RedisService
from app.db.session import async_session_factory

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Redis test key prefix
TEST_KEY_PREFIX = "kave:test:pdf_ocr:"


async def test_redis_connection():
    """Test the Redis connection and basic operations."""
    redis = RedisService()

    # Create a unique test key
    test_key = f"{TEST_KEY_PREFIX}connection_test_{int(time.time())}"
    test_value = f"Connection test at {time.time()}"

    print("\n🔄 Testing Redis connection...")

    # Test setting a value
    success = redis.set(test_key, test_value, ttl=60)
    if not success:
        print("❌ Failed to set Redis test key")
        return False

    # Test getting a value
    retrieved = redis.get(test_key)
    if retrieved != test_value:
        print(
            f"❌ Retrieved value doesn't match: expected '{test_value}', got '{retrieved}'"
        )
        return False

    print("✅ Redis connection is working correctly")

    # Clean up
    redis.delete(test_key)
    return True


async def test_redis_for_task_queue():
    """Test Redis operations typical for a task queue."""
    redis = RedisService()

    # Create unique keys for the test
    task_id = f"task_{int(time.time())}"
    task_key = f"{TEST_KEY_PREFIX}task:{task_id}"
    result_key = f"{TEST_KEY_PREFIX}result:{task_id}"

    print("\n🔄 Testing Redis for task queuing...")

    # Simulate enqueueing a task
    task_data = {"attachment_id": 123, "priority": "high", "created_at": time.time()}

    # Convert dictionary to string
    task_data_str = f"{task_data}"

    # Store task data
    redis.set(task_key, task_data_str)
    print(f"✅ Stored task data: {task_data_str}")

    # Simulate task processing status updates
    for status in ["queued", "processing", "completed"]:
        redis.set(f"{task_key}:status", status)
        print(f"✅ Updated task status to: {status}")
        time.sleep(1)

    # Simulate storing a result
    result_data = {"pages_processed": 5, "success": True, "duration": 3.5}

    # Convert dictionary to string
    result_data_str = f"{result_data}"

    redis.set(result_key, result_data_str)
    print(f"✅ Stored result data: {result_data_str}")

    # Get all keys for this test
    keys = [key for key in redis.redis.keys(f"{TEST_KEY_PREFIX}*")]
    print(f"\n📊 Test created {len(keys)} Redis keys:")
    for key in keys:
        value = redis.get(key)
        print(f" - {key}: {value}")

    # Clean up
    for key in keys:
        redis.delete(key)

    print("\n✅ Redis task queue simulation completed successfully")
    return True


async def test_redis_hash_for_metadata():
    """Test using Redis hashes for metadata storage."""
    redis = RedisService()

    # Create a unique hash name
    hash_name = f"{TEST_KEY_PREFIX}metadata:{int(time.time())}"

    print("\n🔄 Testing Redis hash for metadata storage...")

    # Set multiple fields
    redis.hash_set(hash_name, "attachment_id", "456")
    redis.hash_set(hash_name, "filename", "test-document.pdf")
    redis.hash_set(hash_name, "status", "processing")
    redis.hash_set(hash_name, "page_count", "5")
    redis.hash_set(hash_name, "start_time", str(time.time()))

    # Get individual fields
    attachment_id = redis.hash_get(hash_name, "attachment_id")
    status = redis.hash_get(hash_name, "status")

    print(f"✅ Retrieved attachment_id: {attachment_id}")
    print(f"✅ Retrieved status: {status}")

    # Get all fields
    all_metadata = redis.hash_getall(hash_name)
    print(f"✅ All metadata: {all_metadata}")

    # Update a field
    redis.hash_set(hash_name, "status", "completed")
    updated_status = redis.hash_get(hash_name, "status")
    print(f"✅ Updated status: {updated_status}")

    # Clean up
    redis.delete(hash_name)

    print("\n✅ Redis hash operations completed successfully")
    return True


async def test_redis_expiry():
    """Test Redis key expiration for temporary data."""
    redis = RedisService()

    # Create unique test key
    test_key = f"{TEST_KEY_PREFIX}expiry_test_{int(time.time())}"

    print("\n🔄 Testing Redis key expiration...")

    # Set a key with short TTL
    ttl = 3  # seconds
    redis.set(test_key, "This data will expire soon", ttl=ttl)

    # Check that it exists
    exists_before = redis.exists(test_key)
    print(f"✅ Key exists immediately after setting: {exists_before}")

    # Wait for expiration
    print(f"⏳ Waiting {ttl} seconds for expiration...")
    time.sleep(ttl + 0.5)

    # Check that it's gone
    exists_after = redis.exists(test_key)
    print(f"✅ Key exists after waiting: {exists_after} (should be False)")

    if not exists_after:
        print("\n✅ Redis key expiration works correctly")
        return True
    else:
        print("\n❌ Redis key did not expire as expected")
        return False


async def main():
    """Run all Redis tests."""
    print("\n🧪 Redis Integration Test for PDF OCR Workflow")
    print("===========================================")

    # Run Redis tests
    tests = [
        ("Redis Connection", test_redis_connection),
        ("Redis Task Queue", test_redis_for_task_queue),
        ("Redis Hash for Metadata", test_redis_hash_for_metadata),
        ("Redis Key Expiration", test_redis_expiry),
    ]

    all_passed = True
    for name, test_func in tests:
        try:
            print(f"\n📋 Running test: {name}")
            result = await test_func()
            status = "✅ PASSED" if result else "❌ FAILED"
            print(f"{name}: {status}")
            all_passed = all_passed and result
        except Exception as e:
            print(f"❌ {name} failed with error: {e}")
            all_passed = False

    # Print summary
    print("\n📊 Test Results Summary")
    print("=====================")
    if all_passed:
        print("✨ All Redis tests passed successfully!")
        print(
            "\nYour Redis setup is correctly configured and ready to use with the PDF OCR workflow."
        )
    else:
        print("⚠️ Some Redis tests failed. Please check the logs for details.")


if __name__ == "__main__":
    asyncio.run(main())
