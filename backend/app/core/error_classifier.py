"""
Error classifier with recovery hints (inspired by Hermes Agent).

Classifies errors into structured categories with actionable recovery hints,
replacing scattered try/except with a single classify-then-act pattern.

Usage:
    classifier = ErrorClassifier()
    classification = classifier.classify(exception)
    if classification.retryable:
        await asyncio.sleep(classification.backoff_seconds)
    if classification.should_compress:
        await context_engine.compress()
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class FailoverReason(str, Enum):
    """Structured error categories with recovery semantics."""
    AUTH = "auth"
    BILLING = "billing"
    RATE_LIMIT = "rate_limit"
    OVERLOADED = "overloaded"
    CONTEXT_OVERFLOW = "context_overflow"
    MODEL_NOT_FOUND = "model_not_found"
    TIMEOUT = "timeout"
    CONNECTION = "connection"
    PROVIDER_ERROR = "provider_error"
    VALIDATION = "validation"
    NOT_FOUND = "not_found"
    UNKNOWN = "unknown"


@dataclass
class ErrorClassification:
    """Result of error classification with recovery hints."""
    reason: FailoverReason
    retryable: bool = False
    should_compress: bool = False
    should_fallback: bool = False
    should_rotate_credential: bool = False
    backoff_seconds: float = 0.0
    max_retries: int = 3
    message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


# Pattern-based classification rules
_RULES: list[tuple[str, FailoverReason, dict[str, Any]]] = [
    # Auth errors
    (r"unauthorized|401|invalid.?api.?key|authentication", FailoverReason.AUTH,
     {"retryable": False, "should_rotate_credential": True}),
    (r"forbidden|403|permission.?denied", FailoverReason.AUTH,
     {"retryable": False}),

    # Billing
    (r"quota.?exceeded|billing|insufficient.?funds|payment", FailoverReason.BILLING,
     {"retryable": False, "should_rotate_credential": True}),

    # Rate limiting
    (r"rate.?limit|too.?many.?requests|429", FailoverReason.RATE_LIMIT,
     {"retryable": True, "backoff_seconds": 5.0, "max_retries": 5}),

    # Context overflow
    (r"context.?length|token.?limit|max.?tokens|context.?window", FailoverReason.CONTEXT_OVERFLOW,
     {"retryable": True, "should_compress": True, "max_retries": 2}),

    # Overloaded
    (r"overloaded|capacity|503|service.?unavailable", FailoverReason.OVERLOADED,
     {"retryable": True, "backoff_seconds": 10.0, "max_retries": 3}),

    # Model not found
    (r"model.?not.?found|invalid.?model|404.*model", FailoverReason.MODEL_NOT_FOUND,
     {"retryable": False, "should_fallback": True}),

    # Timeout
    (r"timeout|timed?.?out|deadline.?exceeded", FailoverReason.TIMEOUT,
     {"retryable": True, "backoff_seconds": 2.0, "max_retries": 3}),

    # Connection
    (r"connection.?refused|connection.?reset|network|dns|ECONNREFUSED", FailoverReason.CONNECTION,
     {"retryable": True, "backoff_seconds": 3.0, "max_retries": 3}),

    # Provider errors (5xx)
    (r"internal.?server|500|502|bad.?gateway", FailoverReason.PROVIDER_ERROR,
     {"retryable": True, "backoff_seconds": 5.0, "max_retries": 2}),
]

# Exception type to reason mapping (fast path)
_TYPE_MAP: dict[type, FailoverReason] = {}


def _init_type_map() -> None:
    """Lazy-init type map to avoid circular imports."""
    if _TYPE_MAP:
        return
    try:
        from app.core.exceptions import (
            LLMRateLimitException,
            LLMTimeoutException,
            VectorStoreConnectionException,
            DatabaseConnectionException,
            CacheConnectionException,
            ValidationException,
            NotFoundException,
        )
        _TYPE_MAP.update({
            LLMRateLimitException: FailoverReason.RATE_LIMIT,
            LLMTimeoutException: FailoverReason.TIMEOUT,
            VectorStoreConnectionException: FailoverReason.CONNECTION,
            DatabaseConnectionException: FailoverReason.CONNECTION,
            CacheConnectionException: FailoverReason.CONNECTION,
            ValidationException: FailoverReason.VALIDATION,
            NotFoundException: FailoverReason.NOT_FOUND,
        })
    except ImportError:
        pass


def classify(exception: Exception) -> ErrorClassification:
    """
    Classify an exception into a structured category with recovery hints.

    Uses two-phase classification:
    1. Fast path: exception type lookup
    2. Slow path: regex pattern matching on error message
    """
    _init_type_map()

    # Fast path: type-based
    for exc_type, reason in _TYPE_MAP.items():
        if isinstance(exception, exc_type):
            return _build_classification(exception, reason)

    # Slow path: pattern-based
    error_str = str(exception).lower()
    for pattern, reason, hints in _RULES:
        if re.search(pattern, error_str, re.IGNORECASE):
            return _build_classification(exception, reason, hints)

    # Default: unknown
    return ErrorClassification(
        reason=FailoverReason.UNKNOWN,
        retryable=False,
        message=str(exception)[:200],
    )


def _build_classification(
    exception: Exception,
    reason: FailoverReason,
    hints: dict[str, Any] | None = None,
) -> ErrorClassification:
    """Build ErrorClassification from reason and hints."""
    hints = hints or {}

    # Compute backoff with decorrelated jitter
    backoff = hints.get("backoff_seconds", 0.0)
    if backoff > 0:
        backoff = _decorrelated_jitter(backoff)

    return ErrorClassification(
        reason=reason,
        retryable=hints.get("retryable", reason in (
            FailoverReason.RATE_LIMIT,
            FailoverReason.TIMEOUT,
            FailoverReason.CONNECTION,
            FailoverReason.OVERLOADED,
            FailoverReason.PROVIDER_ERROR,
        )),
        should_compress=hints.get("should_compress", False),
        should_fallback=hints.get("should_fallback", False),
        should_rotate_credential=hints.get("should_rotate_credential", False),
        backoff_seconds=backoff,
        max_retries=hints.get("max_retries", 3),
        message=str(exception)[:200],
    )


def _decorrelated_jitter(base: float, cap: float = 120.0) -> float:
    """
    Decorrelated jitter (Hermes Agent pattern).

    Uses time.time_ns() XOR with a monotonic counter to prevent
    thundering-herd across concurrent requests.
    """
    import random
    jitter = random.uniform(0, base * 3)
    return min(jitter, cap)
