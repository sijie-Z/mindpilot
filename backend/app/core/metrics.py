"""
Prometheus metrics for MindPilot observability.

Exposes metrics for monitoring request latency, throughput,
RAG performance, and system health.
"""
import asyncio
import time
from collections.abc import Callable
from functools import wraps

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, Info, generate_latest
from prometheus_client.utils import INF

# Create a custom registry to avoid conflicts
REGISTRY = CollectorRegistry()

# ============== Counters ==============

REQUEST_COUNT = Counter(
    "mindpilot_http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
    registry=REGISTRY,
)

RAG_RETRIEVAL_COUNT = Counter(
    "mindpilot_rag_retrievals_total",
    "Total RAG retrieval operations",
    ["knowledge_base", "status"],
    registry=REGISTRY,
)

DOCUMENT_PROCESSED_COUNT = Counter(
    "mindpilot_documents_processed_total",
    "Total documents processed",
    ["knowledge_base", "status"],
    registry=REGISTRY,
)

EMBEDDING_COUNT = Counter(
    "mindpilot_embeddings_total",
    "Total embedding operations",
    ["model", "status"],
    registry=REGISTRY,
)

LLM_CALL_COUNT = Counter(
    "mindpilot_llm_calls_total",
    "Total LLM API calls",
    ["model", "status"],
    registry=REGISTRY,
)

TOKEN_USAGE = Counter(
    "mindpilot_tokens_total",
    "Total tokens used",
    ["model", "type"],  # type: prompt, completion
    registry=REGISTRY,
)

CACHE_HIT_COUNT = Counter(
    "mindpilot_cache_hits_total",
    "Cache hit count",
    ["cache_type"],
    registry=REGISTRY,
)

CACHE_MISS_COUNT = Counter(
    "mindpilot_cache_misses_total",
    "Cache miss count",
    ["cache_type"],
    registry=REGISTRY,
)

ERROR_COUNT = Counter(
    "mindpilot_errors_total",
    "Total errors",
    ["error_type", "component"],
    registry=REGISTRY,
)

# ============== Histograms ==============

REQUEST_LATENCY = Histogram(
    "mindpilot_http_request_duration_seconds",
    "HTTP request latency",
    ["method", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0, INF),
    registry=REGISTRY,
)

RETRIEVAL_LATENCY = Histogram(
    "mindpilot_retrieval_duration_seconds",
    "RAG retrieval latency",
    ["knowledge_base"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, INF),
    registry=REGISTRY,
)

EMBEDDING_LATENCY = Histogram(
    "mindpilot_embedding_duration_seconds",
    "Embedding operation latency",
    ["model"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, INF),
    registry=REGISTRY,
)

LLM_LATENCY = Histogram(
    "mindpilot_llm_call_duration_seconds",
    "LLM API call latency",
    ["model"],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, INF),
    registry=REGISTRY,
)

DOCUMENT_PROCESSING_LATENCY = Histogram(
    "mindpilot_document_processing_duration_seconds",
    "Document processing latency",
    ["knowledge_base", "format"],
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, INF),
    registry=REGISTRY,
)

VECTOR_SEARCH_LATENCY = Histogram(
    "mindpilot_vector_search_duration_seconds",
    "Vector search latency",
    ["index_type"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, INF),
    registry=REGISTRY,
)

# ============== Gauges ==============

ACTIVE_SESSIONS = Gauge(
    "mindpilot_active_sessions",
    "Number of active chat sessions",
    registry=REGISTRY,
)

ACTIVE_CONNECTIONS = Gauge(
    "mindpilot_active_connections",
    "Number of active database/vector connections",
    ["component"],
    registry=REGISTRY,
)

KNOWLEDGE_BASE_COUNT = Gauge(
    "mindpilot_knowledge_bases",
    "Number of knowledge bases",
    ["status"],
    registry=REGISTRY,
)

DOCUMENT_COUNT = Gauge(
    "mindpilot_documents",
    "Number of documents",
    ["knowledge_base", "status"],
    registry=REGISTRY,
)

CHUNK_COUNT = Gauge(
    "mindpilot_chunks",
    "Number of chunks",
    ["knowledge_base"],
    registry=REGISTRY,
)

VECTOR_INDEX_SIZE = Gauge(
    "mindpilot_vector_index_size",
    "Size of vector index",
    ["knowledge_base"],
    registry=REGISTRY,
)

CACHE_SIZE = Gauge(
    "mindpilot_cache_size",
    "Cache size in bytes",
    ["cache_type"],
    registry=REGISTRY,
)

# ============== Info ==============

BUILD_INFO = Info(
    "mindpilot_build",
    "Build information",
    registry=REGISTRY,
)

# ============== Helper Functions ==============

def setup_build_info(version: str = "0.1.0", commit: str = "unknown") -> None:
    """Set build information."""
    BUILD_INFO.info({
        "version": version,
        "commit": commit,
    })


def track_request(method: str, endpoint: str, status: int) -> None:
    """Track an HTTP request."""
    REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=str(status)).inc()


def observe_latency(metric: Histogram, labels: dict) -> Callable:
    """Context manager for observing latency."""
    class LatencyObserver:
        def __init__(self, hist: Histogram, lbls: dict):
            self.hist = hist
            self.lbls = lbls
            self.start_time: float | None = None

        def __enter__(self):
            self.start_time = time.perf_counter()
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            if self.start_time is not None:
                elapsed = time.perf_counter() - self.start_time
                self.hist.labels(**self.lbls).observe(elapsed)

    return LatencyObserver(metric, labels)


def time_retrieval(knowledge_base: str):
    """Context manager for timing retrieval operations."""
    return observe_latency(RETRIEVAL_LATENCY, {"knowledge_base": knowledge_base})


def time_embedding(model: str):
    """Context manager for timing embedding operations."""
    return observe_latency(EMBEDDING_LATENCY, {"model": model})


def time_llm_call(model: str):
    """Context manager for timing LLM calls."""
    return observe_latency(LLM_LATENCY, {"model": model})


def time_vector_search(index_type: str = "hnsw"):
    """Context manager for timing vector search."""
    return observe_latency(VECTOR_SEARCH_LATENCY, {"index_type": index_type})


def record_rag_retrieval(knowledge_base: str, success: bool, doc_count: int = 0) -> None:
    """Record a RAG retrieval operation."""
    status = "success" if success else "failure"
    RAG_RETRIEVAL_COUNT.labels(
        knowledge_base=knowledge_base,
        status=status
    ).inc()


def record_embedding(model: str, success: bool, count: int = 1) -> None:
    """Record an embedding operation."""
    status = "success" if success else "failure"
    EMBEDDING_COUNT.labels(model=model, status=status).inc(count)


def record_llm_call(model: str, success: bool) -> None:
    """Record an LLM API call."""
    status = "success" if success else "failure"
    LLM_CALL_COUNT.labels(model=model, status=status).inc()


def record_tokens(model: str, prompt_tokens: int, completion_tokens: int) -> None:
    """Record token usage."""
    TOKEN_USAGE.labels(model=model, type="prompt").inc(prompt_tokens)
    TOKEN_USAGE.labels(model=model, type="completion").inc(completion_tokens)


def record_cache_hit(cache_type: str) -> None:
    """Record a cache hit."""
    CACHE_HIT_COUNT.labels(cache_type=cache_type).inc()


def record_cache_miss(cache_type: str) -> None:
    """Record a cache miss."""
    CACHE_MISS_COUNT.labels(cache_type=cache_type).inc()


def record_error(error_type: str, component: str) -> None:
    """Record an error."""
    ERROR_COUNT.labels(error_type=error_type, component=component).inc()


def update_active_sessions(count: int) -> None:
    """Update active sessions gauge."""
    ACTIVE_SESSIONS.set(count)


def update_knowledge_base_count(active: int, inactive: int) -> None:
    """Update knowledge base count gauges."""
    KNOWLEDGE_BASE_COUNT.labels(status="active").set(active)
    KNOWLEDGE_BASE_COUNT.labels(status="inactive").set(inactive)


def update_document_count(knowledge_base: str, status: str, count: int) -> None:
    """Update document count gauge."""
    DOCUMENT_COUNT.labels(knowledge_base=knowledge_base, status=status).set(count)


def update_chunk_count(knowledge_base: str, count: int) -> None:
    """Update chunk count gauge."""
    CHUNK_COUNT.labels(knowledge_base=knowledge_base).set(count)


def update_vector_index_size(knowledge_base: str, size: int) -> None:
    """Update vector index size."""
    VECTOR_INDEX_SIZE.labels(knowledge_base=knowledge_base).set(size)


def get_metrics() -> bytes:
    """Get Prometheus metrics output."""
    return generate_latest(REGISTRY)


def get_metrics_summary() -> dict:
    """Get a summary of metrics for API response."""
    return {
        "requests_total": REQUEST_COUNT._metrics.get("", 0) if hasattr(REQUEST_COUNT, '_metrics') else 0,
        "active_sessions": ACTIVE_SESSIONS._value.get() if hasattr(ACTIVE_SESSIONS, '_value') else 0,
        "embeddings_total": EMBEDDING_COUNT._metrics.get("", 0) if hasattr(EMBEDDING_COUNT, '_metrics') else 0,
        "llm_calls_total": LLM_CALL_COUNT._metrics.get("", 0) if hasattr(LLM_CALL_COUNT, '_metrics') else 0,
        "cache_hits": CACHE_HIT_COUNT._metrics.get("", 0) if hasattr(CACHE_HIT_COUNT, '_metrics') else 0,
        "cache_misses": CACHE_MISS_COUNT._metrics.get("", 0) if hasattr(CACHE_MISS_COUNT, '_metrics') else 0,
        "errors_total": ERROR_COUNT._metrics.get("", 0) if hasattr(ERROR_COUNT, '_metrics') else 0,
    }


# ============== Decorators ==============

def track_latency(metric: Histogram, **labels):
    """Decorator to track function latency."""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                elapsed = time.perf_counter() - start
                metric.labels(**labels).observe(elapsed)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                elapsed = time.perf_counter() - start
                metric.labels(**labels).observe(elapsed)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def count_calls(metric: Counter, **labels):
    """Decorator to count function calls."""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                result = await func(*args, **kwargs)
                metric.labels(**labels, status="success").inc()
                return result
            except Exception:
                metric.labels(**labels, status="failure").inc()
                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
                metric.labels(**labels, status="success").inc()
                return result
            except Exception:
                metric.labels(**labels, status="failure").inc()
                raise

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


class MetricsMiddleware:
    """
    ASGI middleware for HTTP metrics collection.

    Usage:
        app.add_middleware(MetricsMiddleware)
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope["method"]
        path = scope["path"]

        # Normalize path for metrics (replace IDs)
        normalized_path = self._normalize_path(path)

        start_time = time.perf_counter()
        status_code = 500  # Default to error

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            elapsed = time.perf_counter() - start_time
            track_request(method, normalized_path, status_code)
            REQUEST_LATENCY.labels(method=method, endpoint=normalized_path).observe(elapsed)

    def _normalize_path(self, path: str) -> str:
        """Normalize path by replacing dynamic segments."""
        # Replace UUIDs and numeric IDs
        import re
        path = re.sub(r"/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "/{id}", path)
        path = re.sub(r"/\d+", "/{id}", path)
        return path


# Initialize build info on import
setup_build_info()
