#!/usr/bin/env python3
"""Test script for Redis integration with the running FastAPI application.

This script tests Redis functionality by directly using the RedisService
to verify that Redis operations are working correctly.
"""

import time


def execute_redis_test():
    """Execute the Redis integration test."""
    # Directly use the Redis service to set a test key
    from app.core.redis import RedisService

    redis = RedisService()

    print(f"\n🔍 Testing Redis integration...")

    TEST_KEY = "test:integration:key"

    # Clear any existing test data
    redis.delete(TEST_KEY)

    # Set a test value in Redis
    test_value = f"test_value_{int(time.time())}"
    success = redis.set(TEST_KEY, test_value)
    if not success:
        print(f"❌ Failed to set Redis key")
        return False

    # Read back the value
    retrieved = redis.get(TEST_KEY)
    if retrieved != test_value:
        print(
            f"❌ Retrieved value '{retrieved}' doesn't match set value '{test_value}'"
        )
        return False

    print(f"✅ Successfully set and retrieved Redis value: {test_value}")

    # Test expiration
    print(f"\n🔍 Testing Redis key expiration...")
    expiry_key = f"{TEST_KEY}:expiry"
    expiry_seconds = 2

    redis.set(expiry_key, "expiring-value", ttl=expiry_seconds)
    exists_before = redis.exists(expiry_key)

    print(f"✅ Key set with {expiry_seconds}s expiry. Exists now: {exists_before}")
    print(f"⏱️ Waiting {expiry_seconds} seconds for expiration...")

    time.sleep(expiry_seconds + 0.5)
    exists_after = redis.exists(expiry_key)

    if exists_after:
        print(f"❌ Key still exists after waiting period")
        return False

    print(f"✅ Key has correctly expired")

    # Test increments
    print(f"\n🔍 Testing Redis counter...")
    counter_key = f"{TEST_KEY}:counter"
    redis.delete(counter_key)

    for i in range(1, 6):
        count = redis.incr(counter_key)
        if count != i:
            print(f"❌ Counter value {count} doesn't match expected {i}")
            return False

    print(f"✅ Counter incremented correctly 5 times")

    # Test hash operations
    print(f"\n🔍 Testing Redis hash operations...")
    hash_key = f"{TEST_KEY}:hash"
    redis.delete(hash_key)

    # Set hash fields
    redis.hash_set(hash_key, "username", "testuser")
    redis.hash_set(hash_key, "email", "test@example.com")
    redis.hash_set(hash_key, "role", "tester")

    # Verify individual fields
    username = redis.hash_get(hash_key, "username")
    email = redis.hash_get(hash_key, "email")
    role = redis.hash_get(hash_key, "role")

    if username != "testuser" or email != "test@example.com" or role != "tester":
        print(f"❌ Hash field retrieval failed. Got: {username}, {email}, {role}")
        return False

    # Verify getting all fields
    hash_data = redis.hash_getall(hash_key)
    expected = {"username": "testuser", "email": "test@example.com", "role": "tester"}

    if hash_data != expected:
        print(f"❌ Hash getall failed. Expected: {expected}, Got: {hash_data}")
        return False

    print(f"✅ Hash operations completed successfully")

    # Clean up
    redis.delete(TEST_KEY)
    redis.delete(expiry_key)
    redis.delete(counter_key)
    redis.delete(hash_key)

    print(f"\n✅ Redis integration tests passed successfully!")
    return True


def main():
    """Main test function."""
    print("🧪 Redis Integration Test")
    print("========================")

    execute_redis_test()


if __name__ == "__main__":
    main()
