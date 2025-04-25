#!/usr/bin/env python3
"""Test client for Redis demo API endpoints.

This script tests the Redis demo API endpoints to verify Redis functionality via HTTP.
"""

import json
import time

import requests

# API configuration
API_BASE_URL = "http://127.0.0.1:8000/v1/redis-demo/redis"


def call_api(path, method="GET", data=None, params=None):
    """Call the API and return the response."""
    url = f"{API_BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}

    try:
        if method == "GET":
            response = requests.get(url, params=params, headers=headers)
        elif method == "POST":
            response = requests.post(
                url, data=json.dumps(data) if data else None, headers=headers
            )
        elif method == "DELETE":
            response = requests.delete(url, headers=headers)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

        # Check for HTTP errors
        response.raise_for_status()

        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"API request failed: {e}")
        if hasattr(e, "response") and e.response:
            try:
                print(f"Response: {e.response.json()}")
            except json.JSONDecodeError:
                print(f"Response: {e.response.text}")
        return None


def test_ping():
    """Test the Redis ping endpoint."""
    print("\n🔍 Testing Redis ping...")
    result = call_api("/ping")
    if result and result.get("status") == "ok":
        print(f"✅ Redis ping successful: {result}")
        return True
    else:
        print("❌ Redis ping failed")
        return False


def test_key_operations():
    """Test Redis key operations."""
    print("\n🔍 Testing Redis key operations...")

    # Generate a unique test key
    test_key = f"api:test:key:{int(time.time())}"
    test_value = "Hello from API!"

    # Set a key
    print(f"Setting key {test_key}...")
    result = call_api(
        "/key", method="POST", data={"key": test_key, "value": test_value, "ttl": 60}
    )

    if not result or result.get("status") != "ok":
        print("❌ Failed to set key")
        return False

    print(f"✅ Key set successfully")

    # Get the key
    print(f"Getting key {test_key}...")
    result = call_api(f"/key/{test_key}")

    if not result or not result.get("exists"):
        print("❌ Key does not exist or could not be retrieved")
        return False

    retrieved_value = result.get("value")
    print(f"✅ Retrieved value: {retrieved_value}")

    if retrieved_value != test_value:
        print(
            f"❌ Retrieved value doesn't match: expected '{test_value}', got '{retrieved_value}'"
        )
        return False

    # Delete the key
    print(f"Deleting key {test_key}...")
    result = call_api(f"/key/{test_key}", method="DELETE")

    if not result or result.get("status") != "ok":
        print("❌ Failed to delete key")
        return False

    print(f"✅ Key deleted successfully")

    # Verify the key is gone
    result = call_api(f"/key/{test_key}")

    if result.get("exists"):
        print("❌ Key still exists after deletion")
        return False

    print(f"✅ Key no longer exists after deletion")
    return True


def test_hash_operations():
    """Test Redis hash operations."""
    print("\n🔍 Testing Redis hash operations...")

    # Generate a unique test hash
    hash_name = f"api:test:hash:{int(time.time())}"

    # Set hash fields
    fields = {"username": "apiuser", "email": "api@example.com", "level": "tester"}

    for key, value in fields.items():
        print(f"Setting hash field {key}...")
        result = call_api(
            "/hash", method="POST", data={"name": hash_name, "key": key, "value": value}
        )

        if not result or result.get("status") != "ok":
            print(f"❌ Failed to set hash field {key}")
            return False

    print(f"✅ All hash fields set successfully")

    # Get the hash
    print(f"Getting hash {hash_name}...")
    result = call_api(f"/hash/{hash_name}")

    if not result or not result.get("fields"):
        print("❌ Hash does not exist or has no fields")
        return False

    retrieved_fields = result.get("fields")
    print(f"✅ Retrieved hash fields: {retrieved_fields}")

    if retrieved_fields != fields:
        print(f"❌ Retrieved fields don't match expected fields")
        return False

    print(f"✅ Retrieved hash fields match expected values")

    # Clean up
    for key in fields.keys():
        call_api(f"/key/{hash_name}", method="DELETE")

    return True


def test_counter():
    """Test Redis counter operations."""
    print("\n🔍 Testing Redis counter operations...")

    # Generate a unique counter key
    counter_key = f"api:test:counter:{int(time.time())}"

    # Increment multiple times
    for i in range(1, 6):
        print(f"Increment #{i}...")
        result = call_api(f"/counter/{counter_key}", method="POST")

        if not result or result.get("value") != i:
            print(f"❌ Counter value {result.get('value')} doesn't match expected {i}")
            return False

    print(f"✅ Counter incremented 5 times successfully")

    # Increment by a larger amount
    amount = 10
    print(f"Incrementing by {amount}...")
    # Use data instead of params to send the amount as JSON in the request body
    result = call_api(f"/counter/{counter_key}", method="POST", data={"amount": amount})

    if not result or result.get("value") != 15:
        print(f"❌ Counter value {result.get('value')} doesn't match expected 15")
        return False

    print(f"✅ Counter incremented by {amount} successfully")

    # Clean up
    call_api(f"/key/{counter_key}", method="DELETE")

    return True


def main():
    """Run all tests."""
    print("🧪 Redis API Test Client")
    print("=======================")

    if not test_ping():
        print("❌ Cannot continue: Redis connection test failed")
        return

    # Run all tests
    results = []
    results.append(("Key Operations", test_key_operations()))
    results.append(("Hash Operations", test_hash_operations()))
    results.append(("Counter Operations", test_counter()))

    # Print summary
    print("\n📊 Test Results Summary")
    print("=====================")

    all_passed = True
    for name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{name}: {status}")
        all_passed = all_passed and passed

    if all_passed:
        print("\n✨ All tests passed successfully!")
    else:
        print("\n⚠️  Some tests failed. See above for details.")


if __name__ == "__main__":
    main()
