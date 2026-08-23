"""
Targeted tests to boost coverage for:
- memory_manager.py (53% → 80%+)
- curator.py (22% → 60%+)
- auth.py (58% → 80%+)
- redis_client.py (46% → 65%+)
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ── MemoryManager Tests ──

class TestMemoryManagerExtended:
    """Tests for uncovered memory_manager.py paths."""

    def test_prefetch_with_session_repo(self):
        """prefetch_all loads session history from repo."""
        from app.core.memory_manager import MemoryManager

        mock_repo = AsyncMock()
        mock_repo.get_session = AsyncMock(return_value={
            "messages": [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "hi"}]
        })
        mock_repo.search_messages = AsyncMock(return_value=[])

        manager = MemoryManager(session_repo=mock_repo)
        ctx = asyncio.run(
            manager.prefetch_all("session-1", "user-1", "test query")
        )
        assert len(ctx.session_history) == 2
        mock_repo.get_session.assert_called_once_with("session-1")

    def test_prefetch_with_search_results(self):
        """prefetch_all searches cross-session memories."""
        from app.core.memory_manager import MemoryManager

        mock_repo = AsyncMock()
        mock_repo.get_session = AsyncMock(return_value={"messages": []})
        mock_repo.search_messages = AsyncMock(return_value=[
            {"session_id": "other-session", "content": "Previous answer about Python", "created_at": "2026-05-01"},
        ])

        manager = MemoryManager(session_repo=mock_repo)
        ctx = asyncio.run(
            manager.prefetch_all("session-1", "user-1", "Python")
        )
        assert len(ctx.relevant_memories) == 1
        assert "Python" in ctx.relevant_memories[0]

    def test_prefetch_excludes_current_session(self):
        """prefetch_all excludes memories from current session."""
        from app.core.memory_manager import MemoryManager

        mock_repo = AsyncMock()
        mock_repo.get_session = AsyncMock(return_value={"messages": []})
        mock_repo.search_messages = AsyncMock(return_value=[
            {"session_id": "session-1", "content": "Same session", "created_at": "2026-05-01"},
            {"session_id": "other", "content": "Other session", "created_at": "2026-05-01"},
        ])

        manager = MemoryManager(session_repo=mock_repo)
        ctx = asyncio.run(
            manager.prefetch_all("session-1", "user-1", "test")
        )
        assert len(ctx.relevant_memories) == 1
        assert "Other session" in ctx.relevant_memories[0]

    def test_prefetch_repo_error_handled(self):
        """prefetch_all handles repo errors gracefully."""
        from app.core.memory_manager import MemoryManager

        mock_repo = AsyncMock()
        mock_repo.get_session = AsyncMock(side_effect=Exception("DB error"))
        mock_repo.search_messages = AsyncMock(side_effect=Exception("DB error"))

        manager = MemoryManager(session_repo=mock_repo)
        ctx = asyncio.run(
            manager.prefetch_all("session-1", "user-1", "test")
        )
        assert ctx.session_history == []

    def test_prefetch_caches_context(self):
        """prefetch_all caches the context for sync_all."""
        from app.core.memory_manager import MemoryManager

        manager = MemoryManager()
        asyncio.run(
            manager.prefetch_all("session-1")
        )
        assert "session-1" in manager._cache

    def test_sync_all_updates_cache(self):
        """sync_all adds response to cached session history."""
        from app.core.memory_manager import MemoryManager, MemoryContext

        manager = MemoryManager()
        manager._cache["session-1"] = MemoryContext(
            session_history=[{"role": "user", "content": "hello"}]
        )
        asyncio.run(
            manager.sync_all("session-1", response="hi there")
        )
        assert len(manager._cache["session-1"].session_history) == 2
        assert manager._cache["session-1"].session_history[-1]["content"] == "hi there"

    def test_sync_all_no_cache(self):
        """sync_all does nothing if no cached context."""
        from app.core.memory_manager import MemoryManager
        manager = MemoryManager()
        # Should not raise
        asyncio.run(
            manager.sync_all("nonexistent", response="test")
        )

    def test_compress_history_with_llm(self):
        """_compress_history uses LLM to summarize."""
        from app.core.memory_manager import MemoryManager

        mock_llm = AsyncMock()
        mock_llm.chat = AsyncMock(return_value="Summary of conversation")
        manager = MemoryManager(llm=mock_llm)

        messages = [{"role": "user", "content": f"msg{i}"} for i in range(5)]
        result = asyncio.run(
            manager._compress_history(messages)
        )
        assert result == "Summary of conversation"

    def test_compress_history_llm_failure(self):
        """_compress_history falls back on LLM error."""
        from app.core.memory_manager import MemoryManager

        mock_llm = AsyncMock()
        mock_llm.chat = AsyncMock(side_effect=Exception("LLM down"))
        manager = MemoryManager(llm=mock_llm)

        messages = [{"role": "user", "content": f"msg{i}"} for i in range(5)]
        result = asyncio.run(
            manager._compress_history(messages)
        )
        assert "已压缩" in result

    def test_compress_history_no_llm(self):
        """_compress_history returns empty without LLM."""
        from app.core.memory_manager import MemoryManager
        manager = MemoryManager(llm=None)
        result = asyncio.run(
            manager._compress_history([{"role": "user", "content": "test"}])
        )
        assert result == ""

    def test_clear_cache_specific(self):
        """clear_cache removes specific session."""
        from app.core.memory_manager import MemoryManager, MemoryContext
        manager = MemoryManager()
        manager._cache["s1"] = MemoryContext()
        manager._cache["s2"] = MemoryContext()
        manager.clear_cache("s1")
        assert "s1" not in manager._cache
        assert "s2" in manager._cache

    def test_clear_cache_all(self):
        """clear_cache with no arg clears all."""
        from app.core.memory_manager import MemoryManager, MemoryContext
        manager = MemoryManager()
        manager._cache["s1"] = MemoryContext()
        manager._cache["s2"] = MemoryContext()
        manager.clear_cache()
        assert len(manager._cache) == 0

    def test_memory_context_to_prompt_context(self):
        """MemoryContext.to_prompt_context formats all fields."""
        from app.core.memory_manager import MemoryContext
        ctx = MemoryContext(
            compressed_summary="Previous chat",
            relevant_memories=["Memory 1", "Memory 2"],
            user_preferences={"lang": "zh", "style": "formal"},
        )
        prompt = ctx.to_prompt_context()
        assert "Previous chat" in prompt
        assert "Memory 1" in prompt
        assert "lang: zh" in prompt

    def test_memory_context_empty(self):
        """Empty MemoryContext produces empty prompt."""
        from app.core.memory_manager import MemoryContext
        ctx = MemoryContext()
        assert ctx.to_prompt_context() == ""


# ── Curator Tests ──

class TestCuratorExtended:
    """Tests for uncovered curator.py paths."""

    def test_run_maintenance_success(self):
        """run_maintenance completes with mocked dependencies."""
        from app.core.curator import Curator

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=MagicMock(fetchall=MagicMock(return_value=[])))
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        curator = Curator(vector_store=None, session_repo=None, stale_days=30)
        with patch("app.storage.database.get_db_session", return_value=mock_ctx):
            result = asyncio.run(
                curator.run_maintenance()
            )
        assert result.success is True
        assert result.run_id != ""
        assert result.duration_ms >= 0
        assert curator._run_count == 1

    def test_run_maintenance_with_vector_store(self):
        """run_maintenance with vector store calls consistency check."""
        from app.core.curator import Curator

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=MagicMock(fetchall=MagicMock(return_value=[])))
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        mock_vs = AsyncMock()
        curator = Curator(vector_store=mock_vs, stale_days=30)
        with patch("app.storage.database.get_db_session", return_value=mock_ctx):
            result = asyncio.run(
                curator.run_maintenance()
            )
        assert result.success is True

    def test_run_maintenance_tracks_stats(self):
        """run_maintenance updates internal counters."""
        from app.core.curator import Curator

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=MagicMock(fetchall=MagicMock(return_value=[])))
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        curator = Curator()
        with patch("app.storage.database.get_db_session", return_value=mock_ctx):
            asyncio.run(curator.run_maintenance())
            asyncio.run(curator.run_maintenance())
        assert curator._run_count == 2

    def test_get_stats(self):
        """get_stats returns all expected fields."""
        from app.core.curator import Curator

        curator = Curator(stale_days=60)
        curator._run_count = 5
        curator._total_pruned = 100
        curator._total_fixed = 3
        stats = curator.get_stats()
        assert stats["run_count"] == 5
        assert stats["total_pruned"] == 100
        assert stats["total_fixed"] == 3
        assert stats["stale_days"] == 60

    def test_maintenance_result_success_property(self):
        """MaintenanceResult.success is True when no errors."""
        from app.core.curator import MaintenanceResult

        result = MaintenanceResult(run_id="test")
        assert result.success is True
        result.errors.append("something failed")
        assert result.success is False

    def test_maintenance_result_fields(self):
        """MaintenanceResult stores all fields correctly."""
        from app.core.curator import MaintenanceResult

        result = MaintenanceResult(
            run_id="abc",
            started_at=1000.0,
            completed_at=1001.0,
            duration_ms=1000,
            pruned_chunks=5,
            consolidated_chunks=2,
            consistency_fixes=1,
        )
        assert result.pruned_chunks == 5
        assert result.consolidated_chunks == 2
        assert result.consistency_fixes == 1

    def test_check_consistency_no_vector_store(self):
        """_check_consistency returns 0 without vector store."""
        from app.core.curator import Curator

        curator = Curator(vector_store=None)
        fixes = asyncio.run(
            curator._check_consistency()
        )
        assert fixes == 0


# ── Auth Tests ──

class TestAuthExtended:
    """Tests for uncovered auth.py paths."""

    def test_create_and_verify_token(self):
        """Round-trip: create token then verify it."""
        from app.auth import auth_handler, TokenData

        token = auth_handler.create_access_token({
            "sub": "user-123",
            "username": "testuser",
            "role": "admin",
        })
        data = auth_handler.verify_token(token)
        assert data.user_id == "user-123"
        assert data.username == "testuser"
        assert data.role == "admin"

    def test_create_token_with_custom_expiry(self):
        """create_access_token accepts custom expiry."""
        from app.auth import auth_handler
        from datetime import timedelta

        token = auth_handler.create_access_token(
            {"sub": "user-1"},
            expires_delta=timedelta(minutes=5),
        )
        data = auth_handler.verify_token(token)
        assert data.user_id == "user-1"

    def test_verify_invalid_token(self):
        """verify_token raises on invalid token."""
        from app.auth import auth_handler
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            auth_handler.verify_token("invalid.token.here")
        assert exc_info.value.status_code == 401

    def test_hash_api_key(self):
        """hash_api_key returns consistent SHA256."""
        from app.auth import auth_handler

        h1 = auth_handler.hash_api_key("test-key")
        h2 = auth_handler.hash_api_key("test-key")
        assert h1 == h2
        assert len(h1) == 64  # SHA256 hex

    def test_generate_api_key(self):
        """generate_api_key returns unique keys."""
        from app.auth import auth_handler

        key1 = auth_handler.generate_api_key()
        key2 = auth_handler.generate_api_key()
        assert key1 != key2
        assert len(key1) > 20

    def test_token_data_defaults(self):
        """TokenData has correct defaults."""
        from app.auth import TokenData

        td = TokenData(user_id="u1")
        assert td.role == "user"
        assert td.username is None

    def test_get_optional_user_no_bearer(self):
        """get_optional_user returns None without bearer."""
        from app.auth import get_optional_user

        result = asyncio.run(
            get_optional_user(bearer=None)
        )
        assert result is None

    def test_get_optional_user_invalid_token(self):
        """get_optional_user returns None on invalid token."""
        from app.auth import get_optional_user
        from fastapi.security import HTTPAuthorizationCredentials

        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="bad.token")
        result = asyncio.run(
            get_optional_user(bearer=creds)
        )
        assert result is None

    def test_get_optional_user_valid_token(self):
        """get_optional_user returns TokenData on valid token."""
        from app.auth import auth_handler, get_optional_user
        from fastapi.security import HTTPAuthorizationCredentials

        token = auth_handler.create_access_token({"sub": "u1", "username": "test"})
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        result = asyncio.run(
            get_optional_user(bearer=creds)
        )
        assert result is not None
        assert result.user_id == "u1"

    def test_create_user_token(self):
        """create_user_token helper works correctly."""
        from app.auth import create_user_token, auth_handler

        token = create_user_token("u1", "testuser", "admin")
        data = auth_handler.verify_token(token)
        assert data.user_id == "u1"
        assert data.role == "admin"


# ── RedisClient Tests ──

class TestRedisClientExtended:
    """Tests for uncovered redis_client.py paths."""

    def test_is_connected_false(self):
        """is_connected returns False when not connected."""
        from app.storage.redis_client import RedisClient
        client = RedisClient()
        assert client.is_connected is False

    def test_is_connected_true(self):
        """is_connected returns True when client exists."""
        from app.storage.redis_client import RedisClient
        client = RedisClient()
        client._client = MagicMock()
        assert client.is_connected is True

    def test_client_property_raises_when_not_connected(self):
        """client property raises RuntimeError when not connected."""
        from app.storage.redis_client import RedisClient
        client = RedisClient()
        with pytest.raises(RuntimeError, match="Redis not connected"):
            _ = client.client

    def test_client_property_returns_client(self):
        """client property returns the redis client when connected."""
        from app.storage.redis_client import RedisClient
        client = RedisClient()
        mock = MagicMock()
        client._client = mock
        assert client.client is mock
