"""Redis client utility for the application.

This module provides a Redis client singleton for direct Redis operations
outside of Celery tasks. It leverages the same Redis configuration as Celery.
"""

import logging
from functools import lru_cache
from typing import Any, Optional, Union
from urllib.parse import urlparse

import redis
from redis.exceptions import RedisError

from app.core.config import settings

logger = logging.getLogger(__name__)


@lru_cache
def get_redis_client() -> redis.Redis:
    """
    Get a Redis client instance using application settings.
    
    The client is cached using lru_cache to ensure a singleton instance.
    
    Returns:
        redis.Redis: A configured Redis client instance
    """
    # Use the same Redis URL as Celery broker if available
    redis_url = settings.REDIS_URL or settings.CELERY_BROKER_URL
    
    logger.info(f"Initializing Redis client with URL: {redis_url}")
    
    # Configure connection parameters based on URL scheme
    connection_kwargs = {
        'decode_responses': True,
        'socket_connect_timeout': 10,
        'socket_timeout': 30,
        'retry_on_timeout': True,
        'health_check_interval': 30
    }
    
    # Handle SSL URLs separately
    if redis_url and urlparse(redis_url).scheme == 'rediss':
        logger.info("Using SSL for Redis connection with certificate verification disabled")
        connection_kwargs['ssl_cert_reqs'] = None
    
    try:
        client = redis.Redis.from_url(redis_url, **connection_kwargs)
        # Test the connection
        client.ping()
        logger.info("Redis connection test successful")
        return client
    except RedisError as e:
        logger.error(f"Failed to initialize Redis client: {e}")
        # Still return the client even if ping fails, to allow retry on use
        return redis.Redis.from_url(redis_url, **connection_kwargs)


class RedisService:
    """Service class for Redis operations.
    
    Provides higher-level methods for common Redis operations with
    error handling and logging.
    """
    
    def __init__(self) -> None:
        """Initialize the Redis service with a client."""
        self.redis = get_redis_client()
    
    def set(self, key: str, value: str, ttl: Optional[int] = None) -> bool:
        """
        Set a key-value pair in Redis.
        
        Args:
            key: Redis key
            value: Value to store
            ttl: Time-to-live in seconds (optional)
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            self.redis.set(key, value, ex=ttl)
            return True
        except RedisError as e:
            logger.error(f"Redis set error for key {key}: {e}")
            return False

    def get(self, key: str) -> Optional[str]:
        """
        Get a value from Redis by key.
        
        Args:
            key: Redis key
            
        Returns:
            Optional[str]: The value if found, None otherwise
        """
        try:
            value = self.redis.get(key)
            return value
        except RedisError as e:
            logger.error(f"Redis get error for key {key}: {e}")
            return None
    
    def delete(self, key: str) -> bool:
        """
        Delete a key-value pair from Redis.
        
        Args:
            key: Redis key
            
        Returns:
            bool: True if deleted, False otherwise
        """
        try:
            return bool(self.redis.delete(key))
        except RedisError as e:
            logger.error(f"Redis delete error for key {key}: {e}")
            return False
    
    def exists(self, key: str) -> bool:
        """
        Check if a key exists in Redis.
        
        Args:
            key: Redis key
            
        Returns:
            bool: True if the key exists, False otherwise
        """
        try:
            return bool(self.redis.exists(key))
        except RedisError as e:
            logger.error(f"Redis exists error for key {key}: {e}")
            return False
    
    def incr(self, key: str, amount: int = 1) -> Optional[int]:
        """
        Increment a key's value.
        
        Args:
            key: Redis key
            amount: Amount to increment by (default: 1)
            
        Returns:
            Optional[int]: New value after increment, or None on error
        """
        try:
            return self.redis.incr(key, amount)
        except RedisError as e:
            logger.error(f"Redis incr error for key {key}: {e}")
            return None
    
    def expire(self, key: str, seconds: int) -> bool:
        """
        Set expiration time on a key.
        
        Args:
            key: Redis key
            seconds: Seconds until expiration
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            return bool(self.redis.expire(key, seconds))
        except RedisError as e:
            logger.error(f"Redis expire error for key {key}: {e}")
            return False

    def hash_set(self, name: str, key: str, value: str) -> bool:
        """
        Set a field in a hash stored at key to value.
        
        Args:
            name: Hash name
            key: Field in hash
            value: Value to set
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            self.redis.hset(name, key, value)
            return True
        except RedisError as e:
            logger.error(f"Redis hset error for hash {name}, key {key}: {e}")
            return False
    
    def hash_get(self, name: str, key: str) -> Optional[str]:
        """
        Get the value of a hash field.
        
        Args:
            name: Hash name
            key: Field in hash
            
        Returns:
            Optional[str]: Value if found, None otherwise
        """
        try:
            return self.redis.hget(name, key)
        except RedisError as e:
            logger.error(f"Redis hget error for hash {name}, key {key}: {e}")
            return None
    
    def hash_getall(self, name: str) -> dict[str, str]:
        """
        Get all fields and values in a hash.
        
        Args:
            name: Hash name
            
        Returns:
            dict: Dictionary of field-value pairs
        """
        try:
            return self.redis.hgetall(name) or {}
        except RedisError as e:
            logger.error(f"Redis hgetall error for hash {name}: {e}")
            return {} 