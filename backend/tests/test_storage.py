"""
Tests for storage layer.
Requires MySQL and Redis services to be running.
"""

import pytest


def _check_services() -> str:
    """Check which services are available. Returns '' if all OK, else reason."""
    reasons = []
    import socket

    # Check MySQL
    try:
        s = socket.create_connection(("localhost", 3306), timeout=1.0)
        s.close()
    except Exception:
        reasons.append("MySQL not available on :3306")

    # Check Redis
    try:
        s = socket.create_connection(("localhost", 6379), timeout=1.0)
        s.close()
    except Exception:
        reasons.append("Redis not available on :6379")

    return "; ".join(reasons)


_skip_reason = _check_services()
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(bool(_skip_reason), reason=_skip_reason or "Services available"),
]


class TestDatabaseConnection:
    """Tests for database operations."""

    @pytest.mark.asyncio
    async def test_db_session_context(self):
        """Test database session context manager."""
        from app.storage.database import get_db_session

        async with get_db_session() as db:
            result = await db.execute("SELECT 1")
            assert result.scalar() == 1


class TestRedisClient:
    """Tests for Redis cache operations."""

    @pytest.mark.asyncio
    async def test_redis_connection(self):
        """Test Redis connection."""
        from app.storage.redis_client import redis_client

        await redis_client.connect()
        result = await redis_client.client.ping()
        assert result is True

    @pytest.mark.asyncio
    async def test_redis_session_set_get(self):
        """Test setting and getting session data from Redis."""
        from app.storage.redis_client import redis_client

        await redis_client.connect()

        session_id = "test_session_mindpilot"
        data = {"user_id": "test_user", "history": []}

        await redis_client.set_session(session_id, data, ttl=60)
        result = await redis_client.get_session(session_id)

        assert result == data
        await redis_client.delete_session(session_id)


class TestConsistency:
    """Tests for data consistency."""

    @pytest.mark.asyncio
    async def test_basic_db_query(self):
        """Test basic database query works."""
        from app.storage.database import get_db_session

        async with get_db_session() as db:
            result = await db.execute("SELECT 1 + 1")
            assert result.scalar() == 2
