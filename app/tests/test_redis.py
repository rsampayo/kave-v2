"""Test the Redis service integration."""

import pytest

from app.core.redis import RedisService


def test_redis_service_basics():
    """Test basic Redis operations."""
    redis_service = RedisService()

    test_key = "test:key"
    test_value = "test-value"

    # Clean up any existing test key
    redis_service.delete(test_key)

    # Test key should not exist initially
    assert redis_service.exists(test_key) is False

    # Set the key
    success = redis_service.set(test_key, test_value)
    assert success is True

    # Key should now exist
    assert redis_service.exists(test_key) is True

    # Get the value and verify
    value = redis_service.get(test_key)
    assert value == test_value

    # Delete the key
    success = redis_service.delete(test_key)
    assert success is True

    # Key should no longer exist
    assert redis_service.exists(test_key) is False


def test_redis_service_expiry():
    """Test Redis key expiration."""
    import time

    redis_service = RedisService()

    test_key = "test:expiry"
    test_value = "expiring-value"

    # Clean up any existing test key
    redis_service.delete(test_key)

    # Set key with 1 second TTL
    redis_service.set(test_key, test_value, ttl=1)

    # Key should exist
    assert redis_service.exists(test_key) is True

    # Wait for expiration
    time.sleep(1.1)

    # Key should have expired
    assert redis_service.exists(test_key) is False


def test_redis_increment():
    """Test Redis increment operation."""
    redis_service = RedisService()

    test_key = "test:counter"

    # Clean up any existing test key
    redis_service.delete(test_key)

    # First increment should start at 1
    count = redis_service.incr(test_key)
    assert count == 1

    # Second increment should be 2
    count = redis_service.incr(test_key)
    assert count == 2

    # Increment by 5 should be 7
    count = redis_service.incr(test_key, 5)
    assert count == 7

    # Clean up
    redis_service.delete(test_key)


def test_redis_hash_operations():
    """Test Redis hash operations."""
    redis_service = RedisService()

    test_hash = "test:hash"

    # Clean up any existing test hash
    redis_service.delete(test_hash)

    # Set hash fields
    redis_service.hash_set(test_hash, "field1", "value1")
    redis_service.hash_set(test_hash, "field2", "value2")

    # Get individual fields
    assert redis_service.hash_get(test_hash, "field1") == "value1"
    assert redis_service.hash_get(test_hash, "field2") == "value2"

    # Get all hash fields
    hash_data = redis_service.hash_getall(test_hash)
    assert hash_data == {"field1": "value1", "field2": "value2"}

    # Clean up
    redis_service.delete(test_hash)
