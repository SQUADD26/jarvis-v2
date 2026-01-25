import redis.asyncio as redis
import json
from typing import Any, Optional
from jarvis.config import get_settings
from jarvis.utils.logging import get_logger

logger = get_logger(__name__)


class RedisClient:
    _instance: Optional["RedisClient"] = None
    _client: Optional[redis.Redis] = None
    _connected: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def connect(self):
        """Connect to Redis. Should be called once at application startup."""
        if not self._connected:
            settings = get_settings()
            self._client = redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            self._connected = True
            logger.info("Redis connected")

    async def disconnect(self):
        """Disconnect from Redis. Should be called at application shutdown."""
        if self._client and self._connected:
            await self._client.close()
            self._client = None
            self._connected = False
            logger.info("Redis disconnected")

    def _ensure_connected(self) -> redis.Redis:
        """Get the Redis client, raising if not connected."""
        if not self._connected or not self._client:
            raise RuntimeError("Redis client not connected. Call connect() first.")
        return self._client

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache, returns None if not found or expired."""
        client = self._ensure_connected()
        value = await client.get(key)
        if value:
            return json.loads(value)
        return None

    async def set(self, key: str, value: Any, ttl: int) -> None:
        """Set value in cache with TTL in seconds."""
        client = self._ensure_connected()
        await client.setex(key, ttl, json.dumps(value, default=str))

    async def delete(self, key: str) -> None:
        """Delete key from cache."""
        client = self._ensure_connected()
        await client.delete(key)

    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        client = self._ensure_connected()
        return await client.exists(key) > 0

    async def ttl(self, key: str) -> int:
        """Get remaining TTL for key. Returns -2 if not exists, -1 if no TTL."""
        client = self._ensure_connected()
        return await client.ttl(key)

    async def keys(self, pattern: str) -> list[str]:
        """Get all keys matching pattern."""
        client = self._ensure_connected()
        return await client.keys(pattern)

    async def flush_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern. Returns count deleted."""
        client = self._ensure_connected()
        matched_keys = await client.keys(pattern)
        if matched_keys:
            return await client.delete(*matched_keys)
        return 0


# Singleton instance
redis_client = RedisClient()
