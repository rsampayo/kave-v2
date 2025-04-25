#!/usr/bin/env python3
"""Example script demonstrating Redis usage in the Kave application.

This script shows how to use the RedisService for various Redis operations.
"""

import time
from typing import Any, Dict, cast

from app.core.redis import RedisService


def basic_key_value_example() -> None:
    """Demonstrate basic key-value operations."""
    print("\n=== Basic Key-Value Operations ===")

    redis = RedisService()

    # Set a key
    key = "example:basic:key"
    value = "Hello Redis!"

    redis.set(key, value)
    print(f"Set key '{key}' to '{value}'")

    # Get the key
    retrieved = redis.get(key)
    print(f"Retrieved value: '{retrieved}'")

    # Check if key exists
    exists = redis.exists(key)
    print(f"Key '{key}' exists: {exists}")

    # Delete the key
    redis.delete(key)
    print(f"Deleted key '{key}'")

    # Verify it's gone
    exists = redis.exists(key)
    print(f"Key '{key}' exists after deletion: {exists}")


def ttl_example() -> None:
    """Demonstrate key expiration (TTL)."""
    print("\n=== Key Expiration (TTL) ===")

    redis = RedisService()

    key = "example:ttl:key"
    value = "This will expire in 5 seconds"
    ttl = 5

    # Set key with TTL
    redis.set(key, value, ttl=ttl)
    print(f"Set key '{key}' with TTL of {ttl} seconds")

    # Check if it exists
    exists = redis.exists(key)
    print(f"Key '{key}' exists immediately after setting: {exists}")

    # Wait and check again
    print(f"Waiting {ttl} seconds for expiration...")
    time.sleep(ttl)

    exists = redis.exists(key)
    print(f"Key '{key}' exists after {ttl} seconds: {exists}")


def counter_example() -> None:
    """Demonstrate counter (increment) operations."""
    print("\n=== Counter Operations ===")

    redis = RedisService()

    key = "example:counter"

    # Clean up any previous example
    redis.delete(key)

    # Increment the counter multiple times
    for i in range(1, 6):
        count = redis.incr(key)
        print(f"Increment #{i}: counter value is now {count}")

    # Increment by a larger amount
    count = redis.incr(key, 10)
    print(f"After incrementing by 10: counter value is now {count}")

    # Clean up
    redis.delete(key)


def hash_example() -> None:
    """Demonstrate hash operations."""
    print("\n=== Hash Operations ===")

    redis = RedisService()

    hash_name = "example:user:profile"

    # Clean up any previous example
    redis.delete(hash_name)

    # Set multiple fields in a hash
    redis.hash_set(hash_name, "username", "johndoe")
    redis.hash_set(hash_name, "email", "john@example.com")
    redis.hash_set(hash_name, "age", "30")

    print(f"Created hash '{hash_name}' with three fields")

    # Get individual fields
    username = redis.hash_get(hash_name, "username")
    email = redis.hash_get(hash_name, "email")

    print(f"Retrieved username: {username}")
    print(f"Retrieved email: {email}")

    # Get all fields
    profile = redis.hash_getall(hash_name)
    print(f"Full profile hash: {profile}")

    # Update a field
    redis.hash_set(hash_name, "age", "31")
    print("Updated age to 31")

    # Get updated profile
    profile = redis.hash_getall(hash_name)
    print(f"Updated profile hash: {profile}")

    # Clean up
    redis.delete(hash_name)


def rate_limiting_example() -> None:
    """Demonstrate a simple rate limiting implementation."""
    print("\n=== Rate Limiting Example ===")

    redis = RedisService()

    # Parameters
    user_id = "user123"
    max_requests = 5
    window_seconds = 10

    def check_rate_limit(user: str) -> bool:
        """Check if user exceeds rate limit.

        Args:
            user: User identifier

        Returns:
            bool: True if user is within rate limit, False otherwise
        """
        key = f"ratelimit:{user}"

        # Get current count
        count = cast(int, redis.incr(key, 1) or 0)

        # Set expiry if this is the first request in the window
        if count == 1:
            redis.expire(key, window_seconds)

        return count <= max_requests

    # Simulate multiple API requests
    for i in range(1, 8):
        allowed = check_rate_limit(user_id)
        print(
            f"Request #{i} for user '{user_id}': {'Allowed' if allowed else 'BLOCKED'}"
        )

        # Small delay between requests
        time.sleep(0.5)

    # Wait for rate limit window to reset
    remaining_time = window_seconds - (0.5 * 7)
    if remaining_time > 0:
        print(f"Waiting {remaining_time:.1f} seconds for rate limit window to reset...")
        time.sleep(remaining_time)

    # Should be allowed again
    allowed = check_rate_limit(user_id)
    print(
        f"Request after reset for user '{user_id}': {'Allowed' if allowed else 'BLOCKED'}"
    )

    # Clean up
    redis.delete(f"ratelimit:{user_id}")


if __name__ == "__main__":
    print("Redis Usage Examples")
    print("====================")

    basic_key_value_example()
    ttl_example()
    counter_example()
    hash_example()
    rate_limiting_example()

    print("\nAll examples completed.")
