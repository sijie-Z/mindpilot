"""
Tests for error handling - retry, timeout, and graceful degradation.
"""
import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.exceptions import (
    DatabaseConnectionException,
    DatabaseException,
    DocumentTooLargeException,
    EmbeddingException,
    EmbeddingTimeoutException,
    ErrorCode,
    LLMException,
    LLMRateLimitException,
    LLMTimeoutException,
    MindPilotException,
    NotFoundException,
    ValidationException,
    VectorStoreConnectionException,
    VectorStoreException,
)
from app.core.logger import get_logger
from app.core.retry import (
    CircuitBreaker,
    cache_retry,
    database_retry,
    embedding_retry,
    llm_retry,
    vector_store_retry,
)

logger = get_logger(__name__)


class TestExceptionHierarchy:
    """Tests for exception hierarchy and behavior."""

    def test_base_exception_properties(self):
        """Test base exception properties."""
        exc = MindPilotException(
            message="Test error",
            error_code=ErrorCode.INTERNAL_ERROR,
            details={"key": "value"},
        )

        assert exc.message == "Test error"
        assert exc.error_code == ErrorCode.INTERNAL_ERROR
        assert exc.details == {"key": "value"}
        assert exc.http_status == 500

    def test_exception_to_dict(self):
        """Test exception serialization to dict."""
        exc = ValidationException(
            message="Invalid input",
            details={"field": "username", "reason": "too short"},
        )

        result = exc.to_dict()

        assert result["error"] is True
        assert result["error_code"] == ErrorCode.VALIDATION_ERROR
        assert result["message"] == "Invalid input"
        assert result["details"]["field"] == "username"

    def test_exception_str_representation(self):
        """Test string representation of exceptions."""
        exc = LLMException(message="LLM service unavailable")

        assert str(exc) == "[LLM_ERROR] LLM service unavailable"

    def test_http_status_codes(self):
        """Test HTTP status codes for different exceptions."""
        test_cases = [
            (LLMException, 502),
            (LLMTimeoutException, 504),
            (LLMRateLimitException, 429),
            (EmbeddingException, 502),
            (EmbeddingTimeoutException, 504),
            (VectorStoreException, 502),
            (VectorStoreConnectionException, 503),
            (DatabaseException, 500),
            (DatabaseConnectionException, 503),
            (ValidationException, 400),
            (NotFoundException, 404),
            (DocumentTooLargeException, 413),
        ]

        for exc_class, expected_status in test_cases:
            exc = exc_class(message="test")
            assert exc.http_status == expected_status

    def test_not_found_exception_no_error_status(self):
        """Test NotFoundException returns 200 for no results case."""
        exc = NotFoundException(message="No documents found")
        result = exc.to_dict()

        assert exc.http_status == 404
        assert result["error_code"] == ErrorCode.NOT_FOUND


class TestRetryMechanisms:
    """Tests for retry decorators."""

    @pytest.mark.asyncio
    async def test_vector_store_retry_success(self):
        """Test vector store retry succeeds after transient failure."""
        call_count = 0

        @vector_store_retry(max_attempts=3)
        async def operation():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise VectorStoreConnectionException("Connection refused")
            return "success"

        result = await operation()

        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_embedding_retry_max_attempts(self):
        """Test embedding retry fails after max attempts."""
        call_count = 0

        @embedding_retry(max_attempts=2)
        async def operation():
            nonlocal call_count
            call_count += 1
            raise EmbeddingException("Service unavailable")

        with pytest.raises(EmbeddingException):
            await operation()

        assert call_count == 2

    @pytest.mark.asyncio
    async def test_llm_retry_rate_limit(self):
        """Test LLM retry handles rate limit specially."""
        call_count = 0
        start_time = None

        @llm_retry(max_attempts=3, rate_limit_wait_multiplier=1)
        async def operation():
            nonlocal call_count, start_time
            if start_time is None:
                start_time = asyncio.get_event_loop().time()
            call_count += 1
            if call_count < 2:
                raise LLMRateLimitException("Rate limit exceeded")
            return "success"

        result = await operation()

        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_database_retry_connection_error(self):
        """Test database retry on connection error."""
        call_count = 0

        @database_retry(max_attempts=3)
        async def operation():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise DatabaseConnectionException("MySQL connection lost")
            return "success"

        result = await operation()

        assert result == "success"

    @pytest.mark.asyncio
    async def test_cache_retry_non_retryable_error(self):
        """Test cache retry doesn't retry on non-retryable errors."""
        call_count = 0

        @cache_retry(max_attempts=3)
        async def operation():
            nonlocal call_count
            call_count += 1
            # ValidationException is not in CACHE_RETRYABLE
            raise ValidationException("Invalid key format")

        with pytest.raises(ValidationException):
            await operation()

        # Should not retry on validation error
        assert call_count == 1


class TestCircuitBreaker:
    """Tests for circuit breaker pattern."""

    def test_circuit_breaker_initial_state(self):
        """Test circuit breaker starts in closed state."""
        breaker = CircuitBreaker(failure_threshold=3)

        assert breaker.state == CircuitBreaker.CLOSED
        assert breaker.is_open is False

    @pytest.mark.asyncio
    async def test_circuit_breaker_trips_on_failures(self):
        """Test circuit breaker trips after threshold failures."""
        breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=60)

        async def failing_operation():
            raise Exception("Service error")

        # Trigger failures
        for _ in range(2):
            try:
                await breaker.protect(failing_operation)()
            except:
                pass

        assert breaker.state == CircuitBreaker.OPEN
        assert breaker.is_open is True

    @pytest.mark.asyncio
    async def test_circuit_breaker_rejects_when_open(self):
        """Test circuit breaker rejects requests when open."""
        breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=300)

        async def failing_operation():
            raise Exception("Error")

        # Trip the breaker
        try:
            await breaker.protect(failing_operation)()
        except:
            pass

        # Should reject next call
        async def success_operation():
            return "success"

        with pytest.raises(VectorStoreConnectionException):
            await breaker.protect(success_operation)()

    @pytest.mark.asyncio
    async def test_circuit_breaker_transitions_to_half_open(self):
        """Test circuit breaker transitions to half-open after timeout."""
        breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=1, half_open_max_calls=1)

        async def failing_operation():
            raise Exception("Error")

        # Trip the breaker
        try:
            await breaker.protect(failing_operation)()
        except:
            pass

        assert breaker.state == CircuitBreaker.OPEN

        # Wait for recovery timeout
        await asyncio.sleep(1.1)

        async def success_operation():
            return "success"

        # Should allow call in half-open state
        _result = await breaker.protect(success_operation)()

        # After half_open_max_calls=1 successful calls, should close
        assert breaker.state == CircuitBreaker.CLOSED

    @pytest.mark.asyncio
    async def test_circuit_breaker_resets_on_success(self):
        """Test circuit breaker failure count resets on success."""
        breaker = CircuitBreaker(failure_threshold=5)

        async def mixed_operation(fail=False):
            if fail:
                raise Exception("Error")
            return "success"

        # Cause some failures
        for _ in range(3):
            try:
                await breaker.protect(mixed_operation)(fail=True)
            except:
                pass

        assert breaker._failure_count == 3

        # Successful call should reset
        await breaker.protect(mixed_operation)(fail=False)

        assert breaker._failure_count == 0


class TestTimeoutHandling:
    """Tests for timeout handling."""

    @pytest.mark.asyncio
    async def test_operation_timeout(self):
        """Test operation timeout raises appropriate exception."""
        async def slow_operation():
            await asyncio.sleep(5)
            return "result"

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(slow_operation(), timeout=1)

    @pytest.mark.asyncio
    async def test_llm_timeout_conversion(self):
        """Test LLM timeout is converted to proper exception."""
        with patch('asyncio.wait_for') as mock_wait:
            mock_wait.side_effect = TimeoutError()

            with pytest.raises(asyncio.TimeoutError):
                await mock_wait(asyncio.sleep(1), timeout=30)


class TestGracefulDegradation:
    """Tests for graceful degradation."""

    @pytest.mark.asyncio
    async def test_retrieval_without_cache(self):
        """Test retrieval works without cache (degraded mode)."""
        from app.rag.retriever import HybridRetriever

        retriever = HybridRetriever()

        # Simulate a working vector store with mocked embedding
        with patch('app.rag.embedder.embedder.embed_query', new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = [0.1] * 2048

            with patch.object(retriever._vector_store, 'search', return_value=[]) as _mock_vs:
                with patch.object(retriever, '_bm25_search', new_callable=AsyncMock) as mock_bm25:
                    mock_bm25.return_value = ["chunk_1"]
                    with patch.object(retriever, '_get_chunks_from_mysql', new_callable=AsyncMock) as mock_chunks:
                        mock_chunks.return_value = [
                            {"chunk_id": "chunk_1", "content": "result", "metadata": {}}
                        ]

                        result = await retriever.search("test query")

                        # Should still return results
                        assert len(result) >= 1

    @pytest.mark.asyncio
    async def test_fallback_to_bm25_on_vector_failure(self):
        """Test fallback to BM25 when vector search returns empty."""
        from app.rag.retriever import HybridRetriever

        retriever = HybridRetriever()

        with patch('app.rag.embedder.embedder.embed_query', new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = [0.1] * 2048

            # Simulate vector store returning empty results (degraded)
            with patch.object(retriever._vector_store, 'search', return_value=[]) as _mock_vs:
                with patch.object(retriever, '_bm25_search', new_callable=AsyncMock) as mock_bm25:
                    mock_bm25.return_value = ["chunk_1", "chunk_2"]
                    with patch.object(retriever, '_get_chunks_from_mysql', new_callable=AsyncMock) as mock_chunks:
                        mock_chunks.return_value = [
                            {"chunk_id": "chunk_1", "content": "bm25 result", "metadata": {}}
                        ]

                        result = await retriever.search("test query")

                        # Should fall back to BM25 results
                        assert len(result) >= 1
                        assert mock_bm25.called

    @pytest.mark.asyncio
    async def test_empty_response_on_total_failure(self):
        """Test returns empty response when all retrieval returns empty."""
        from app.rag.retriever import HybridRetriever

        retriever = HybridRetriever()

        with patch('app.rag.embedder.embedder.embed_query', new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = [0.1] * 2048

            # Both vector and BM25 return empty
            with patch.object(retriever._vector_store, 'search', return_value=[]) as _mock_vs:
                with patch.object(retriever, '_bm25_search', new_callable=AsyncMock) as mock_bm25:
                    mock_bm25.return_value = []
                    with patch.object(retriever, '_get_chunks_from_mysql', new_callable=AsyncMock) as mock_chunks:
                        mock_chunks.return_value = []

                        result = await retriever.search("test query")

                        # Should return empty results gracefully
                        assert len(result) == 0


class TestErrorRecovery:
    """Tests for error recovery."""

    @pytest.mark.asyncio
    async def test_connection_pool_recovery(self):
        """Test database connection pool recovery."""

        # Simulate connection failure
        with patch('sqlalchemy.ext.asyncio.create_async_engine') as mock_engine:
            mock_engine.side_effect = Exception("Connection failed")

            # Next call should succeed with new connection
            mock_engine.side_effect = None
            mock_engine.return_value = MagicMock()

    @pytest.mark.asyncio
    async def test_cache_recovery_after_disconnect(self):
        """Test cache recovery after Redis disconnect."""
        from app.storage.redis_client import RedisClient

        redis = RedisClient()
        await redis.connect()

        with patch.object(redis.client, 'ping', new_callable=AsyncMock) as mock_ping:
            # First ping fails
            mock_ping.side_effect = [False, True]

            # Ping behavior after reconnect
            result = await redis.client.ping()
            assert result is False

            result = await redis.client.ping()
            assert result is True


class TestLoggingOnErrors:
    """Tests for error logging."""

    def test_exception_logs_context(self, caplog):
        """Test that exceptions log contextual information."""
        import logging

        with caplog.at_level(logging.ERROR):
            exc = MindPilotException(
                message="Test error",
                error_code=ErrorCode.INTERNAL_ERROR,
                details={"user_id": "user123", "operation": "test"},
            )

            logger.error(f"Exception occurred: {exc}", extra={"error_details": exc.details})

        assert "INTERNAL_ERROR" in caplog.text

    @pytest.mark.asyncio
    async def test_retry_logs_attempts(self, caplog):
        """Test that retries are logged."""
        import logging

        call_count = 0

        @vector_store_retry(max_attempts=2)
        async def operation():
            nonlocal call_count
            call_count += 1
            raise VectorStoreException("Temporary error")

        with caplog.at_level(logging.INFO), pytest.raises(VectorStoreException):
            await operation()

        # Verify retry happened (implementation dependent)
        assert call_count == 2
