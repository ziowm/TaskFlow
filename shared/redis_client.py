import redis
import os
from typing import Optional


class RedisClient:
    """Redis connection utility with error handling"""
    
    def __init__(self, redis_url: Optional[str] = None):
        """
        Initialize Redis client
        
        Args:
            redis_url: Redis connection string (default: from REDIS_URL env var or redis://localhost:6379)
        """
        self.redis_url = redis_url or os.getenv('REDIS_URL', 'redis://localhost:6379')
        self._client: Optional[redis.Redis] = None
    
    def connect(self) -> redis.Redis:
        """
        Establish connection to Redis
        
        Returns:
            Redis client instance
            
        Raises:
            redis.ConnectionError: If connection fails
        """
        if self._client is None:
            self._client = redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            # Test connection
            self._client.ping()
        
        return self._client
    
    def get_client(self) -> redis.Redis:
        """
        Get Redis client, connecting if necessary
        
        Returns:
            Redis client instance
        """
        if self._client is None:
            return self.connect()
        return self._client
    
    def close(self):
        """Close Redis connection"""
        if self._client:
            self._client.close()
            self._client = None
    
    def is_connected(self) -> bool:
        """
        Check if Redis connection is active
        
        Returns:
            True if connected, False otherwise
        """
        try:
            if self._client:
                self._client.ping()
                return True
        except (redis.ConnectionError, redis.TimeoutError):
            pass
        return False
