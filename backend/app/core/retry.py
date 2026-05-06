"""
Retry mechanisms for MindPilot using tenacity.

Provides configurable retry decorators for external service calls,
with support for different retry strategies per service type.
"""
import asyncio
import logging
from collections.abc import Callable
from functools import wraps
from typing import Any

from tenacity import (
    after_log,
    before_sleep_log,
    retry,
    retry_if_exception,
    retry_if_exception_type,
    retry_if_result,
    stop_after_attempt,
    stop_after_delay,
    wait_exponential,
    wait_fixed,
    wait_random,
)

from app.core.exceptions import (
    CacheConnectionException,
    CacheException,
    DatabaseConnectionException,
    DatabaseException,
    EmbeddingException,
    LLMRateLimitException,
    LLMTimeoutException,
    VectorStoreConnectionException,
    VectorStoreException,
)
from app.core.logger import get_logger

logger = get_logger(__name__)


# Retryable exceptions for each service type
VECTOR_STORE_RETRYABLE: tuple[type[Exception], ...] = (
    VectorStoreConnectionException,
    VectorStoreException,
    ConnectionError,
    TimeoutError,
)

EMBEDDING_RETRYABLE: tuple[type[Exception], ...] = (
    EmbeddingException,
    ConnectionError,
    TimeoutError,
)

LLM_RETRYABLE: tuple[type[Exception], ...] = (
    LLMTimeoutException,
    LLMRateLimitException,
    ConnectionError,
    TimeoutError,
)

DATABASE_RETRYABLE: tuple[type[Exception], ...] = (
    DatabaseConnectionException,
    DatabaseException,
    ConnectionError,
)

CACHE_RETRYABLE: tuple[type[Exception], ...] = (
    CacheConnectionException,
    CacheException,
    ConnectionError,
)


def is_rate_limit_error(exception: Exception) -> bool:
    """Check if exception is a rate limit error."""
    return isinstance(exception, LLMRateLimitException) or (
        "rate limit" in str(exception).lower()
    )


def is_transient_error(exception: Exception) -> bool:
    """Check if exception is a transient/retryable error."""
    transient_keywords = [
        "connection",
        "timeout",
        "temporarily",
        "unavailable",
        "overloaded",
        "retry",
    ]
    error_str = str(exception).lower()
    return any(keyword in error_str for keyword in transient_keywords)


# Default retry configurations
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_MAX_WAIT_SECONDS = 30
DEFAULT_EXP_MULTIPLIER = 1
DEFAULT_EXP_MIN_WAIT = 1
DEFAULT_EXP_MAX_WAIT = 10


def vector_store_retry(
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    max_wait_seconds: int = DEFAULT_MAX_WAIT_SECONDS,
) -> Callable:
    """
    Retry decorator for vector store operations (Milvus/FAISS).

    Uses exponential backoff with random jitter for connection errors.

    Args:
        max_attempts: Maximum number of retry attempts
        max_wait_seconds: Maximum total wait time in seconds

    Returns:
        Decorated function with retry logic
    """
    return retry(
        retry=retry_if_exception_type(VECTOR_STORE_RETRYABLE),
        stop=(stop_after_attempt(max_attempts) | stop_after_delay(max_wait_seconds)),
        wait=wait_exponential(
            multiplier=DEFAULT_EXP_MULTIPLIER,
            min=DEFAULT_EXP_MIN_WAIT,
            max=DEFAULT_EXP_MAX_WAIT,
        ) + wait_random(0, 2),
        before_sleep=before_sleep_log(logger.logger, logging.INFO),
        after=after_log(logger.logger, logging.INFO),
        reraise=True,
    )


def embedding_retry(
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    max_wait_seconds: int = DEFAULT_MAX_WAIT_SECONDS,
) -> Callable:
    """
    Retry decorator for embedding operations.

    Uses exponential backoff for API timeouts and connection errors.

    Args:
        max_attempts: Maximum number of retry attempts
        max_wait_seconds: Maximum total wait time in seconds

    Returns:
        Decorated function with retry logic
    """
    return retry(
        retry=retry_if_exception_type(EMBEDDING_RETRYABLE),
        stop=(stop_after_attempt(max_attempts) | stop_after_delay(max_wait_seconds)),
        wait=wait_exponential(
            multiplier=DEFAULT_EXP_MULTIPLIER,
            min=DEFAULT_EXP_MIN_WAIT,
            max=DEFAULT_EXP_MAX_WAIT,
        ),
        before_sleep=before_sleep_log(logger.logger, logging.INFO),
        after=after_log(logger.logger, logging.INFO),
        reraise=True,
    )


def llm_retry(
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    max_wait_seconds: int = DEFAULT_MAX_WAIT_SECONDS,
    rate_limit_wait_multiplier: int = 5,
) -> Callable:
    """
    Retry decorator for LLM operations.

    Uses longer wait for rate limits, exponential backoff for other errors.

    Args:
        max_attempts: Maximum number of retry attempts
        max_wait_seconds: Maximum total wait time in seconds
        rate_limit_wait_multiplier: Multiplier for rate limit wait time

    Returns:
        Decorated function with retry logic
    """
    def wait_strategy(retry_state: Any) -> float:
        """Custom wait strategy based on error type."""
        exception = retry_state.outcome.exception()
        if is_rate_limit_error(exception):
            # Longer wait for rate limits
            return wait_fixed(rate_limit_wait_multiplier * retry_state.attempt_number)(retry_state)
        return wait_exponential(
            multiplier=DEFAULT_EXP_MULTIPLIER,
            min=DEFAULT_EXP_MIN_WAIT,
            max=DEFAULT_EXP_MAX_WAIT,
        )(retry_state)

    return retry(
        retry=retry_if_exception_type(LLM_RETRYABLE),
        stop=(stop_after_attempt(max_attempts) | stop_after_delay(max_wait_seconds)),
        wait=wait_strategy,
        before_sleep=before_sleep_log(logger.logger, logging.INFO),
        after=after_log(logger.logger, logging.INFO),
        reraise=True,
    )


def database_retry(
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    max_wait_seconds: int = DEFAULT_MAX_WAIT_SECONDS,
) -> Callable:
    """
    Retry decorator for database operations (MySQL).

    Uses exponential backoff for connection errors.

    Args:
        max_attempts: Maximum number of retry attempts
        max_wait_seconds: Maximum total wait time in seconds

    Returns:
        Decorated function with retry logic
    """
    return retry(
        retry=retry_if_exception_type(DATABASE_RETRYABLE),
        stop=(stop_after_attempt(max_attempts) | stop_after_delay(max_wait_seconds)),
        wait=wait_exponential(
            multiplier=DEFAULT_EXP_MULTIPLIER,
            min=DEFAULT_EXP_MIN_WAIT,
            max=DEFAULT_EXP_MAX_WAIT,
        ),
        before_sleep=before_sleep_log(logger.logger, logging.INFO),
        after=after_log(logger.logger, logging.INFO),
        reraise=True,
    )


def cache_retry(
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    max_wait_seconds: int = DEFAULT_MAX_WAIT_SECONDS,
) -> Callable:
    """
    Retry decorator for cache operations (Redis).

    Uses exponential backoff for connection errors.

    Args:
        max_attempts: Maximum number of retry attempts
        max_wait_seconds: Maximum total wait time in seconds

    Returns:
        Decorated function with retry logic
    """
    return retry(
        retry=retry_if_exception_type(CACHE_RETRYABLE),
        stop=(stop_after_attempt(max_attempts) | stop_after_delay(max_wait_seconds)),
        wait=wait_exponential(
            multiplier=DEFAULT_EXP_MULTIPLIER,
            min=DEFAULT_EXP_MIN_WAIT,
            max=DEFAULT_EXP_MAX_WAIT,
        ),
        before_sleep=before_sleep_log(logger.logger, logging.INFO),
        after=after_log(logger.logger, logging.INFO),
        reraise=True,
    )


def with_retry(
    retryable_exceptions: tuple[type[Exception], ...],
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    max_wait_seconds: int = DEFAULT_MAX_WAIT_SECONDS,
) -> Callable:
    """
    Generic retry decorator with custom exception types.

    Args:
        retryable_exceptions: Tuple of exception types to retry on
        max_attempts: Maximum number of retry attempts
        max_wait_seconds: Maximum total wait time in seconds

    Returns:
        Decorated function with retry logic
    """
    return retry(
        retry=retry_if_exception_type(retryable_exceptions),
        stop=(stop_after_attempt(max_attempts) | stop_after_delay(max_wait_seconds)),
        wait=wait_exponential(
            multiplier=DEFAULT_EXP_MULTIPLIER,
            min=DEFAULT_EXP_MIN_WAIT,
            max=DEFAULT_EXP_MAX_WAIT,
        ),
        before_sleep=before_sleep_log(logger.logger, logging.INFO),
        after=after_log(logger.logger, logging.INFO),
        reraise=True,
    )


def retry_on_result(
    predicate: Callable[[Any], bool],
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    wait_seconds: int = 1,
) -> Callable:
    """
    Retry decorator based on result value, not exception.

    Useful for operations that return None or empty results on failure.

    Args:
        predicate: Function that returns True if result should trigger retry
        max_attempts: Maximum number of retry attempts
        wait_seconds: Fixed wait between attempts

    Returns:
        Decorated function with retry logic
    """
    return retry(
        retry=retry_if_exception(lambda e: False) | retry_if_result(predicate),
        stop=stop_after_attempt(max_attempts),
        wait=wait_fixed(wait_seconds),
        before_sleep=before_sleep_log(logger.logger, logging.INFO),
        reraise=True,
    )


# Async-compatible retry wrappers
def async_vector_store_retry(**kwargs: Any) -> Callable:
    """Async-compatible retry for vector store operations."""
    return vector_store_retry(**kwargs)


def async_embedding_retry(**kwargs: Any) -> Callable:
    """Async-compatible retry for embedding operations."""
    return embedding_retry(**kwargs)


def async_llm_retry(**kwargs: Any) -> Callable:
    """Async-compatible retry for LLM operations."""
    return llm_retry(**kwargs)


def async_database_retry(**kwargs: Any) -> Callable:
    """Async-compatible retry for database operations."""
    return database_retry(**kwargs)


def async_cache_retry(**kwargs: Any) -> Callable:
    """Async-compatible retry for cache operations."""
    return cache_retry(**kwargs)


# Circuit breaker pattern (simple implementation)
class CircuitBreaker:
    """
    Simple circuit breaker for preventing cascading failures.

    States:
    - CLOSED: Normal operation, requests flow through
    - OPEN: Circuit tripped, requests fail immediately
    - HALF_OPEN: Testing if service recovered, limited requests

    Usage:
        breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60)

        @breaker.protect
        async def call_external_service():
            ...
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        half_open_max_calls: int = 3,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self._state = self.CLOSED
        self._failure_count = 0
        self._last_failure_time: float | None = None
        self._half_open_calls = 0

    def protect(self, func: Callable) -> Callable:
        """Wrap function with circuit breaker protection."""
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            return await self._call(func, *args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            return self._call_sync(func, *args, **kwargs)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    async def _call(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """Execute async function with circuit breaker logic."""
        if self._state == self.OPEN:
            if self._should_attempt_recovery():
                self._state = self.HALF_OPEN
                self._half_open_calls = 0
            else:
                raise VectorStoreConnectionException(
                    "Circuit breaker is open, service unavailable"
                )

        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception:
            self._on_failure()
            raise

    def _call_sync(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """Execute sync function with circuit breaker logic."""
        if self._state == self.OPEN:
            if self._should_attempt_recovery():
                self._state = self.HALF_OPEN
                self._half_open_calls = 0
            else:
                raise VectorStoreConnectionException(
                    "Circuit breaker is open, service unavailable"
                )

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception:
            self._on_failure()
            raise

    def _should_attempt_recovery(self) -> bool:
        """Check if circuit should transition to half-open."""
        if self._last_failure_time is None:
            return True
        import time
        elapsed = time.time() - self._last_failure_time
        return elapsed >= self.recovery_timeout

    def _on_success(self) -> None:
        """Handle successful call."""
        if self._state == self.HALF_OPEN:
            self._half_open_calls += 1
            if self._half_open_calls >= self.half_open_max_calls:
                self._state = self.CLOSED
                self._failure_count = 0
                logger.info("Circuit breaker recovered, state: CLOSED")
        elif self._state == self.CLOSED:
            self._failure_count = 0

    def _on_failure(self) -> None:
        """Handle failed call."""
        import time
        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._state == self.HALF_OPEN:
            self._state = self.OPEN
            logger.warning(
                f"Circuit breaker tripped again during recovery, state: OPEN, "
                f"failures: {self._failure_count}"
            )
        elif self._failure_count >= self.failure_threshold:
            self._state = self.OPEN
            logger.warning(
                f"Circuit breaker tripped, state: OPEN, "
                f"failures: {self._failure_count}"
            )

    @property
    def state(self) -> str:
        """Get current circuit breaker state."""
        return self._state

    @property
    def is_open(self) -> bool:
        """Check if circuit is open."""
        return self._state == self.OPEN


# Global circuit breaker instances for different services
vector_store_breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60)
embedding_breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60)
llm_breaker = CircuitBreaker(failure_threshold=10, recovery_timeout=120)
database_breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=30)
cache_breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=30)
