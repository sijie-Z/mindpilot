"""
Rate limiting middleware for MindPilot API.

Implements sliding window rate limiting using Redis.
"""
import time
from collections.abc import Callable

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logger import get_logger
from app.storage.redis_client import redis_client

logger = get_logger(__name__)


class RateLimitConfig:
    """Rate limit configuration for different endpoints."""

    # Default limits: (max_requests, window_seconds)
    DEFAULT_LIMITS = {
        "/api/chat/": (100, 60),  # 100 requests per minute
        "/api/chat/stream": (30, 60),  # 30 streams per minute
        "/api/document/upload": (10, 60),  # 10 uploads per minute
        "/api/knowledge/": (30, 60),  # 30 requests per minute
        "/api/auth/login": (10, 60),  # 10 login attempts per minute
        "/api/auth/register": (5, 60),  # 5 registrations per minute
    }

    # More lenient limits for authenticated users
    AUTHENTICATED_MULTIPLIER = 2

    def __init__(
        self,
        default_limit: tuple = (60, 60),
        authenticated_multiplier: float = 2.0,
    ):
        self.default_limit = default_limit
        self.authenticated_multiplier = authenticated_multiplier


class RateLimiter:
    """
    Sliding window rate limiter using Redis.

    Uses sorted sets for accurate sliding window implementation.
    """

    def __init__(self, redis_client):
        self.redis = redis_client

    async def is_allowed(
        self,
        key: str,
        max_requests: int,
        window_seconds: int,
    ) -> tuple[bool, int, float]:
        """
        Check if request is allowed using sliding window algorithm.

        Args:
            key: Redis key for this rate limit
            max_requests: Maximum allowed requests in window
            window_seconds: Time window in seconds

        Returns:
            Tuple of (is_allowed, remaining_requests, retry_after_seconds)
        """
        now = time.time()
        window_start = now - window_seconds

        try:
            client = self.redis.client

            # Use Redis pipeline for atomic operations
            pipe = client.pipeline()

            # Remove old entries outside the window
            pipe.zremrangebyscore(key, 0, window_start)

            # Count current requests in window
            pipe.zcard(key)

            # Execute pipeline
            results = await pipe.execute()
            current_count = results[1]

            if current_count >= max_requests:
                # Get the oldest request time to calculate retry_after
                oldest = await client.zrange(key, 0, 0, withscores=True)
                if oldest:
                    oldest_time = oldest[0][1]
                    retry_after = oldest_time + window_seconds - now
                    return False, 0, max(0, retry_after)
                return False, 0, window_seconds

            # Add current request
            await client.zadd(key, {str(now): now})

            # Set expiry on the key
            await client.expire(key, window_seconds)

            remaining = max_requests - current_count - 1
            return True, remaining, 0

        except Exception as e:
            logger.warning(f"Rate limit check failed: {e}, allowing request")
            # On Redis error, allow the request (fail open)
            return True, max_requests, 0

    async def get_usage(self, key: str, window_seconds: int) -> int:
        """Get current usage count for a key."""
        now = time.time()
        window_start = now - window_seconds

        try:
            client = self.redis.client
            await client.zremrangebyscore(key, 0, window_start)
            return await client.zcard(key)
        except Exception:
            return 0


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware for FastAPI.

    Adds rate limit headers to responses:
    - X-RateLimit-Limit: Maximum requests per window
    - X-RateLimit-Remaining: Remaining requests in current window
    - X-RateLimit-Reset: Unix timestamp when window resets

    Returns 429 Too Many Requests when limit exceeded.
    """

    def __init__(
        self,
        app,
        config: RateLimitConfig | None = None,
        key_func: Callable | None = None,
    ):
        super().__init__(app)
        self.config = config or RateLimitConfig()
        self.limiter = RateLimiter(redis_client)
        self.key_func = key_func or self._default_key_func

    def _default_key_func(self, request: Request) -> str:
        """Generate rate limit key from request."""
        # Use IP address as default key
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            ip = forwarded.split(",")[0].strip()
        else:
            ip = request.client.host if request.client else "unknown"

        # Include user ID if authenticated
        user_id = request.headers.get("X-User-ID", "")
        if user_id:
            return f"rate_limit:user:{user_id}"

        return f"rate_limit:ip:{ip}"

    def _get_limit_for_path(self, path: str) -> tuple:
        """Get rate limit for a specific path."""
        for pattern, limit in self.config.DEFAULT_LIMITS.items():
            if path.startswith(pattern):
                return limit
        return self.config.default_limit

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health checks and metrics
        if request.url.path.startswith("/health") or request.url.path == "/":
            return await call_next(request)

        # Skip for OPTIONS requests (CORS preflight)
        if request.method == "OPTIONS":
            return await call_next(request)

        # Get rate limit configuration for this path
        max_requests, window_seconds = self._get_limit_for_path(request.url.path)

        # Check if user is authenticated (increase limit)
        auth_header = request.headers.get("Authorization", "")
        is_authenticated = auth_header.startswith("Bearer ")
        if is_authenticated:
            max_requests = int(max_requests * self.config.authenticated_multiplier)

        # Generate rate limit key
        key = self.key_func(request) + f":{request.url.path}"

        # Check rate limit
        is_allowed, remaining, retry_after = await self.limiter.is_allowed(
            key, max_requests, window_seconds
        )

        # Prepare headers
        headers = {
            "X-RateLimit-Limit": str(max_requests),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(int(time.time() + window_seconds)),
        }

        if not is_allowed:
            headers["Retry-After"] = str(int(retry_after) + 1)

            logger.warning(
                f"Rate limit exceeded for {key}",
                extra={
                    "path": request.url.path,
                    "ip": request.client.host if request.client else None,
                    "retry_after": retry_after,
                }
            )

            return JSONResponse(
                status_code=429,
                content={
                    "error": True,
                    "error_code": "RATE_LIMIT_EXCEEDED",
                    "message": "请求过于频繁，请稍后再试",
                    "retry_after": int(retry_after) + 1,
                },
                headers=headers,
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers to response
        for key, value in headers.items():
            response.headers[key] = value

        return response


def get_rate_limit_key(request: Request) -> str:
    """
    Custom key function for rate limiting.
    Can be customized based on requirements.
    """
    # Use API key if present
    api_key = request.headers.get("X-API-Key")
    if api_key:
        return f"rate_limit:api_key:{api_key}"

    # Use user ID if authenticated
    user_id = request.headers.get("X-User-ID")
    if user_id:
        return f"rate_limit:user:{user_id}"

    # Fall back to IP address
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
    else:
        ip = request.client.host if request.client else "unknown"

    return f"rate_limit:ip:{ip}"


# Decorator for rate limiting specific endpoints
def rate_limit(max_requests: int, window_seconds: int = 60):
    """
    Decorator to apply rate limiting to specific endpoints.

    Usage:
        @router.get("/endpoint")
        @rate_limit(10, 60)
        async def my_endpoint():
            ...
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Extract request from args
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break

            if request:
                key = get_rate_limit_key(request) + f":{request.url.path}"
                limiter = RateLimiter(redis_client)

                is_allowed, remaining, retry_after = await limiter.is_allowed(
                    key, max_requests, window_seconds
                )

                if not is_allowed:
                    raise HTTPException(
                        status_code=429,
                        detail={
                            "error_code": "RATE_LIMIT_EXCEEDED",
                            "message": "请求过于频繁，请稍后再试",
                            "retry_after": int(retry_after) + 1,
                        }
                    )

            return await func(*args, **kwargs)

        return wrapper
    return decorator
