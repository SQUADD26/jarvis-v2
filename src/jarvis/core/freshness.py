from jarvis.db.redis_client import redis_client
from jarvis.config import get_settings
from jarvis.utils.logging import get_logger

logger = get_logger(__name__)


class FreshnessChecker:
    """Check and manage data freshness in cache."""

    CACHE_KEYS = {
        "calendar": "jarvis:cache:calendar:{user_id}",
        "email": "jarvis:cache:email:{user_id}",
        "web": "jarvis:cache:web:{query_hash}"
    }

    def __init__(self):
        self.settings = get_settings()
        self.ttls = {
            "calendar": self.settings.cache_ttl_calendar,
            "email": self.settings.cache_ttl_email,
            "web": self.settings.cache_ttl_web
        }

    async def is_fresh(self, resource: str, user_id: str, query_hash: str = None) -> bool:
        """Check if cached data is still fresh."""
        key = self._get_key(resource, user_id, query_hash)
        exists = await redis_client.exists(key)
        return exists

    async def get_cached(self, resource: str, user_id: str, query_hash: str = None) -> dict | None:
        """Get cached data if fresh."""
        key = self._get_key(resource, user_id, query_hash)
        return await redis_client.get(key)

    async def set_cache(
        self,
        resource: str,
        user_id: str,
        data: dict,
        query_hash: str = None
    ) -> None:
        """Cache data with appropriate TTL."""
        key = self._get_key(resource, user_id, query_hash)
        ttl = self.ttls.get(resource, 300)
        await redis_client.set(key, data, ttl)
        logger.debug(f"Cached {resource} for {user_id}, TTL={ttl}s")

    async def invalidate(self, resource: str, user_id: str) -> None:
        """Force invalidate cache for a resource."""
        pattern = self.CACHE_KEYS[resource].format(user_id=user_id, query_hash="*")
        deleted = await redis_client.flush_pattern(pattern)
        logger.info(f"Invalidated {deleted} cache entries for {resource}")

    async def check_all(self, user_id: str, resources: list[str]) -> dict[str, bool]:
        """Check freshness for multiple resources."""
        result = {}
        for resource in resources:
            result[resource] = not await self.is_fresh(resource, user_id)
        return result

    def _get_key(self, resource: str, user_id: str, query_hash: str = None) -> str:
        """Generate cache key."""
        template = self.CACHE_KEYS.get(resource, "jarvis:cache:{resource}:{user_id}")
        return template.format(
            resource=resource,
            user_id=user_id,
            query_hash=query_hash or "default"
        )


# Singleton
freshness = FreshnessChecker()
