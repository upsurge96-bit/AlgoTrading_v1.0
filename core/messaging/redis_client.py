"""
Redis Client Module
------------------
Redis client implementation for messaging and caching.
"""

import os
import logging
import json
from typing import Any, Dict, List, Optional, Union
from datetime import timedelta

# Try to import redis, provide useful error if it's not installed
try:
    import redis
except ImportError:
    raise ImportError("Redis client requires 'redis' package. Install it with 'pip install redis'.")

# Configure logging
logger = logging.getLogger("redis_client")

# Check if Redis is enabled via environment variable
REDIS_ENABLED = os.environ.get("ENABLE_REDIS", "true").lower() in ["true", "1", "yes", "y"]

class RedisClient:
    """
    Redis client for caching and messaging.
    
    This client provides a wrapper around the redis library with additional
    functionality specific to the application requirements.
    """
    
    def __init__(self, 
                 host: str = None, 
                 port: int = None, 
                 password: str = None,
                 db: int = 0,
                 socket_timeout: int = 5,
                 socket_connect_timeout: int = 5,
                 socket_keepalive: bool = True,
                 decode_responses: bool = True):
        """
        Initialize Redis client.
        
        Args:
            host: Redis server hostname
            port: Redis server port
            password: Redis server password
            db: Redis database number
            socket_timeout: Socket timeout in seconds
            socket_connect_timeout: Socket connection timeout in seconds
            socket_keepalive: Whether to enable socket keepalive
            decode_responses: Whether to decode byte responses to str
        """
        # Use parameters from environment if not provided
        self.host = host or os.environ.get("REDIS_HOST", "localhost")
        self.port = port or int(os.environ.get("REDIS_PORT", 6379))
        self.password = password or os.environ.get("REDIS_PASSWORD", None)
        self.db = db
        
        # Connection settings
        self.socket_timeout = socket_timeout
        self.socket_connect_timeout = socket_connect_timeout
        self.socket_keepalive = socket_keepalive
        self.decode_responses = decode_responses
        
        # Initialize connection
        self._client = None
        self._initialize_connection()
    
    def _initialize_connection(self) -> None:
        """Initialize Redis connection."""
        # If Redis is disabled, don't try to connect
        if not REDIS_ENABLED:
            logger.info("Redis integration is disabled via ENABLE_REDIS=false")
            self._client = None
            return
            
        try:
            self._client = redis.Redis(
                host=self.host,
                port=self.port,
                password=self.password,
                db=self.db,
                socket_timeout=self.socket_timeout,
                socket_connect_timeout=self.socket_connect_timeout,
                socket_keepalive=self.socket_keepalive,
                decode_responses=self.decode_responses
            )
            
            # Test connection
            self._client.ping()
            logger.info(f"Connected to Redis at {self.host}:{self.port}")
            
        except redis.ConnectionError as e:
            logger.warning(f"Failed to connect to Redis: {e}")
            # Keep the client but it will fail on operations
            # This allows the application to start without Redis
            # and try again later
        
        except Exception as e:
            logger.error(f"Error initializing Redis client: {e}")
            # Don't raise exception, set client to None instead
            self._client = None
    
    def _ensure_connection(self) -> bool:
        """
        Ensure Redis connection is active.
        
        Returns:
            True if connection is active, False otherwise
        """
        if self._client is None:
            self._initialize_connection()
            
        if self._client is None:
            return False
            
        try:
            self._client.ping()
            return True
        except:
            # Try to reconnect
            try:
                self._initialize_connection()
                return self._client is not None
            except:
                return False
    
    def get(self, key: str) -> Optional[str]:
        """
        Get value for key.
        
        Args:
            key: Key to get
            
        Returns:
            Value for key or None if not found
        """
        if not self._ensure_connection():
            logger.warning(f"Redis not available, get operation failed for key: {key}")
            return None
            
        try:
            return self._client.get(key)
        except Exception as e:
            logger.error(f"Error getting value for key {key}: {e}")
            return None
    
    def set(self, key: str, value: str, expire: Optional[int] = None) -> bool:
        """
        Set key to value with optional expiry.
        
        Args:
            key: Key to set
            value: Value to set
            expire: Expiry in seconds
            
        Returns:
            True if successful, False otherwise
        """
        if not self._ensure_connection():
            logger.warning(f"Redis not available, set operation failed for key: {key}")
            return False
            
        try:
            if expire is not None:
                return self._client.setex(key, expire, value)
            else:
                return self._client.set(key, value)
        except Exception as e:
            logger.error(f"Error setting value for key {key}: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """
        Delete key.
        
        Args:
            key: Key to delete
            
        Returns:
            True if key was deleted, False otherwise
        """
        if not self._ensure_connection():
            logger.warning(f"Redis not available, delete operation failed for key: {key}")
            return False
            
        try:
            return self._client.delete(key) > 0
        except Exception as e:
            logger.error(f"Error deleting key {key}: {e}")
            return False
    
    def exists(self, key: str) -> bool:
        """
        Check if key exists.
        
        Args:
            key: Key to check
            
        Returns:
            True if key exists, False otherwise
        """
        if not self._ensure_connection():
            logger.warning(f"Redis not available, exists operation failed for key: {key}")
            return False
            
        try:
            return self._client.exists(key) > 0
        except Exception as e:
            logger.error(f"Error checking if key {key} exists: {e}")
            return False
    
    def expire(self, key: str, seconds: int) -> bool:
        """
        Set expiry on key.
        
        Args:
            key: Key to set expiry on
            seconds: Expiry in seconds
            
        Returns:
            True if expiry was set, False otherwise
        """
        if not self._ensure_connection():
            logger.warning(f"Redis not available, expire operation failed for key: {key}")
            return False
            
        try:
            return self._client.expire(key, seconds)
        except Exception as e:
            logger.error(f"Error setting expiry for key {key}: {e}")
            return False
    
    def ttl(self, key: str) -> int:
        """
        Get time to live for key.
        
        Args:
            key: Key to get TTL for
            
        Returns:
            TTL in seconds or -1 if key has no expiry or -2 if key does not exist
        """
        if not self._ensure_connection():
            logger.warning(f"Redis not available, ttl operation failed for key: {key}")
            return -2
            
        try:
            return self._client.ttl(key)
        except Exception as e:
            logger.error(f"Error getting TTL for key {key}: {e}")
            return -2
    
    def hget(self, key: str, field: str) -> Optional[str]:
        """
        Get value for hash field.
        
        Args:
            key: Hash key
            field: Field in hash
            
        Returns:
            Value for field or None if not found
        """
        if not self._ensure_connection():
            logger.warning(f"Redis not available, hget operation failed for key: {key}, field: {field}")
            return None
            
        try:
            return self._client.hget(key, field)
        except Exception as e:
            logger.error(f"Error getting value for key {key}, field {field}: {e}")
            return None
    
    def hset(self, key: str, field: str, value: str) -> bool:
        """
        Set hash field to value.
        
        Args:
            key: Hash key
            field: Field in hash
            value: Value to set
            
        Returns:
            True if field was new, False otherwise
        """
        if not self._ensure_connection():
            logger.warning(f"Redis not available, hset operation failed for key: {key}, field: {field}")
            return False
            
        try:
            return self._client.hset(key, field, value) > 0
        except Exception as e:
            logger.error(f"Error setting value for key {key}, field {field}: {e}")
            return False
    
    def hdel(self, key: str, field: str) -> bool:
        """
        Delete hash field.
        
        Args:
            key: Hash key
            field: Field in hash
            
        Returns:
            True if field was deleted, False otherwise
        """
        if not self._ensure_connection():
            logger.warning(f"Redis not available, hdel operation failed for key: {key}, field: {field}")
            return False
            
        try:
            return self._client.hdel(key, field) > 0
        except Exception as e:
            logger.error(f"Error deleting field {field} from key {key}: {e}")
            return False
    
    def hkeys(self, key: str) -> List[str]:
        """
        Get all fields in hash.
        
        Args:
            key: Hash key
            
        Returns:
            List of fields in hash
        """
        if not self._ensure_connection():
            logger.warning(f"Redis not available, hkeys operation failed for key: {key}")
            return []
            
        try:
            return self._client.hkeys(key)
        except Exception as e:
            logger.error(f"Error getting fields for key {key}: {e}")
            return []
    
    def hgetall(self, key: str) -> Dict[str, str]:
        """
        Get all fields and values in hash.
        
        Args:
            key: Hash key
            
        Returns:
            Dictionary of field-value pairs
        """
        if not self._ensure_connection():
            logger.warning(f"Redis not available, hgetall operation failed for key: {key}")
            return {}
            
        try:
            return self._client.hgetall(key)
        except Exception as e:
            logger.error(f"Error getting all fields and values for key {key}: {e}")
            return {}
    
    def json_get(self, key: str) -> Any:
        """
        Get JSON value for key.
        
        Args:
            key: Key to get
            
        Returns:
            Decoded JSON value or None if not found
        """
        value = self.get(key)
        if value is None:
            return None
            
        try:
            return json.loads(value)
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON for key {key}: {e}")
            return None
    
    def json_set(self, key: str, value: Any, expire: Optional[int] = None) -> bool:
        """
        Set key to JSON value with optional expiry.
        
        Args:
            key: Key to set
            value: Value to encode as JSON and set
            expire: Expiry in seconds
            
        Returns:
            True if successful, False otherwise
        """
        try:
            json_value = json.dumps(value)
            return self.set(key, json_value, expire)
        except Exception as e:
            logger.error(f"Error encoding JSON for key {key}: {e}")
            return False
    
    def publish(self, channel: str, message: str) -> int:
        """
        Publish message to channel.
        
        Args:
            channel: Channel to publish to
            message: Message to publish
            
        Returns:
            Number of clients that received the message
        """
        if not self._ensure_connection():
            logger.warning(f"Redis not available, publish operation failed for channel: {channel}")
            return 0
            
        try:
            return self._client.publish(channel, message)
        except Exception as e:
            logger.error(f"Error publishing message to channel {channel}: {e}")
            return 0
    
    def json_publish(self, channel: str, message: Any) -> int:
        """
        Publish JSON message to channel.
        
        Args:
            channel: Channel to publish to
            message: Message to encode as JSON and publish
            
        Returns:
            Number of clients that received the message
        """
        try:
            json_message = json.dumps(message)
            return self.publish(channel, json_message)
        except Exception as e:
            logger.error(f"Error encoding JSON for channel {channel}: {e}")
            return 0
    
    def incr(self, key: str, amount: int = 1) -> Optional[int]:
        """
        Increment key by amount.
        
        Args:
            key: Key to increment
            amount: Amount to increment by
            
        Returns:
            New value or None if operation failed
        """
        if not self._ensure_connection():
            logger.warning(f"Redis not available, incr operation failed for key: {key}")
            return None
            
        try:
            return self._client.incrby(key, amount)
        except Exception as e:
            logger.error(f"Error incrementing key {key}: {e}")
            return None
    
    def decr(self, key: str, amount: int = 1) -> Optional[int]:
        """
        Decrement key by amount.
        
        Args:
            key: Key to decrement
            amount: Amount to decrement by
            
        Returns:
            New value or None if operation failed
        """
        if not self._ensure_connection():
            logger.warning(f"Redis not available, decr operation failed for key: {key}")
            return None
            
        try:
            return self._client.decrby(key, amount)
        except Exception as e:
            logger.error(f"Error decrementing key {key}: {e}")
            return None
    
    def close(self) -> None:
        """Close Redis connection."""
        if self._client:
            try:
                self._client.close()
                logger.info("Redis connection closed")
            except Exception as e:
                logger.error(f"Error closing Redis connection: {e}")