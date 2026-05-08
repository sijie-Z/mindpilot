"""
Redis client for caching and session management.
"""
import json
from typing import Any

import redis.asyncio as redis

from app.config import settings


class RedisClient:
    """Redis client wrapper."""

    def __init__(self):
        self._client: redis.Redis | None = None

    @property
    def is_connected(self) -> bool:
        """Check if Redis client is connected."""
        return self._client is not None

    async def connect(self):
        """Connect to Redis."""
        self._client = redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )

    async def disconnect(self):
        """Disconnect from Redis."""
        if self._client:
            await self._client.close()

    @property
    def client(self) -> redis.Redis:
        if not self._client:
            raise RuntimeError("Redis not connected")
        return self._client

    # Session management
    async def set_session(self, session_id: str, data: dict, ttl: int = 86400):
        """Store session data with TTL (default 24 hours)."""
        await self.client.setex(
            f"session:{session_id}",
            ttl,
            json.dumps(data),
        )

    async def get_session(self, session_id: str) -> dict | None:
        """Get session data."""
        data = await self.client.get(f"session:{session_id}")
        return json.loads(data) if data else None

    async def delete_session(self, session_id: str):
        """Delete session."""
        await self.client.delete(f"session:{session_id}")

    # Query cache
    async def cache_query(self, query_hash: str, result: dict, ttl: int = 3600):
        """Cache query result (default 1 hour)."""
        await self.client.setex(
            f"query_cache:{query_hash}",
            ttl,
            json.dumps(result),
        )

    async def get_cached_query(self, query_hash: str) -> dict | None:
        """Get cached query result."""
        data = await self.client.get(f"query_cache:{query_hash}")
        return json.loads(data) if data else None

    # Skill result cache
    async def cache_skill_result(
        self,
        skill_name: str,
        params_hash: str,
        result: Any,
        ttl: int = 1800
    ):
        """Cache skill execution result (default 30 minutes)."""
        await self.client.setex(
            f"skill_cache:{skill_name}:{params_hash}",
            ttl,
            json.dumps(result),
        )

    async def get_cached_skill_result(
        self,
        skill_name: str,
        params_hash: str
    ) -> Any | None:
        """Get cached skill result."""
        data = await self.client.get(f"skill_cache:{skill_name}:{params_hash}")
        return json.loads(data) if data else None

    # Rate limiting
    async def check_rate_limit(
        self,
        key: str,
        max_requests: int,
        window_seconds: int
    ) -> tuple[bool, int]:
        """
        Check rate limit using sliding window.
        Returns (is_allowed, remaining_requests).
        """
        current = await self.client.get(key)

        if current is None:
            await self.client.setex(key, window_seconds, 1)
            return True, max_requests - 1

        current = int(current)
        if current >= max_requests:
            return False, 0

        await self.client.incr(key)
        return True, max_requests - current - 1


# Global Redis client instance
redis_client = RedisClient()
