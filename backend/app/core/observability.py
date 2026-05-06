"""
LangFuse integration for observability.
Provides tracing, monitoring, and token consumption tracking.
"""
import os
import time
import uuid
from functools import wraps
from typing import Any

from app.core.logger import get_logger

logger = get_logger(__name__)

# Check if LangFuse is enabled
LANGFUSE_ENABLED = bool(os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"))

if LANGFUSE_ENABLED:
    try:
        from langfuse import Langfuse

        langfuse_client = Langfuse(
            public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
            secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
            host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
        )
        logger.info("LangFuse initialized successfully")
    except ImportError:
        LANGFUSE_ENABLED = False
        logger.warning("LangFuse package not installed, observability disabled")
else:
    langfuse_client = None
    logger.info("LangFuse not configured, observability disabled")


class TraceContext:
    """Context manager for tracing operations."""

    def __init__(self, name: str, metadata: dict[str, Any] = None):
        self.name = name
        self.metadata = metadata or {}
        self.trace_id = str(uuid.uuid4())
        self.span_id = str(uuid.uuid4())
        self.start_time = None
        self.end_time = None
        self.trace = None
        self.span = None

    def __enter__(self):
        self.start_time = time.time()

        if LANGFUSE_ENABLED and langfuse_client:
            try:
                self.trace = langfuse_client.trace(
                    id=self.trace_id,
                    name=self.name,
                    metadata=self.metadata,
                )
            except Exception as e:
                logger.debug(f"Failed to create trace: {e}")

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.time()
        duration_ms = int((self.end_time - self.start_time) * 1000)

        if self.trace:
            try:
                self.trace.update(
                    output={"duration_ms": duration_ms},
                    metadata={"status": "error" if exc_type else "success"}
                )
            except Exception as e:
                logger.debug(f"Failed to update trace: {e}")

        return False  # Don't suppress exceptions

    def add_event(self, name: str, input_data: Any = None, output_data: Any = None, metadata: dict = None):
        """Add an event to the trace."""
        if not LANGFUSE_ENABLED or not self.trace:
            return

        try:
            self.trace.event(
                name=name,
                input=input_data,
                output=output_data,
                metadata=metadata or {},
            )
        except Exception as e:
            logger.debug(f"Failed to add event: {e}")

    def add_span(self, name: str, input_data: Any = None, output_data: Any = None,
                 start_time: float = None, end_time: float = None, level: str = "DEFAULT"):
        """Add a span to the trace."""
        if not LANGFUSE_ENABLED or not self.trace:
            return

        try:
            self.trace.span(
                name=name,
                input=input_data,
                output=output_data,
                start_time=start_time,
                end_time=end_time,
                level=level,
            )
        except Exception as e:
            logger.debug(f"Failed to add span: {e}")


class ObservabilityManager:
    """
    Manager for observability and tracing.
    Provides a unified interface for tracking operations.
    """

    def __init__(self):
        self.enabled = LANGFUSE_ENABLED
        self.client = langfuse_client

    def create_trace(self, name: str, user_id: str = None, session_id: str = None,
                     metadata: dict[str, Any] = None) -> TraceContext:
        """Create a new trace context."""
        ctx = TraceContext(name, metadata)
        if user_id:
            ctx.metadata["user_id"] = user_id
        if session_id:
            ctx.metadata["session_id"] = session_id
        return ctx

    def track_llm_call(
        self,
        model: str,
        prompt: str,
        completion: str,
        tokens_input: int = 0,
        tokens_output: int = 0,
        latency_ms: int = 0,
        trace_id: str = None,
    ):
        """Track an LLM API call."""
        if not self.enabled or not self.client:
            return

        try:
            generation = self.client.generation(
                name="llm_call",
                model=model,
                input=prompt,
                output=completion,
                usage={
                    "input": tokens_input,
                    "output": tokens_output,
                    "total": tokens_input + tokens_output,
                },
                metadata={
                    "latency_ms": latency_ms,
                },
            )
            return generation
        except Exception as e:
            logger.debug(f"Failed to track LLM call: {e}")

    def track_embedding(
        self,
        model: str,
        texts: list[str],
        latency_ms: int = 0,
        trace_id: str = None,
    ):
        """Track an embedding API call."""
        if not self.enabled or not self.client:
            return

        try:
            embedding = self.client.embedding(
                name="embedding",
                model=model,
                input=texts,
                metadata={
                    "text_count": len(texts),
                    "latency_ms": latency_ms,
                },
            )
            return embedding
        except Exception as e:
            logger.debug(f"Failed to track embedding: {e}")

    def track_retrieval(
        self,
        query: str,
        results: list[dict],
        latency_ms: int = 0,
        metadata: dict = None,
    ):
        """Track a retrieval operation."""
        if not self.enabled or not self.client:
            return

        try:
            retrieval = self.client.retrieval(
                name="retrieval",
                input=query,
                output=results,
                metadata={
                    "result_count": len(results),
                    "latency_ms": latency_ms,
                    **(metadata or {}),
                },
            )
            return retrieval
        except Exception as e:
            logger.debug(f"Failed to track retrieval: {e}")

    def track_rag_pipeline(
        self,
        query: str,
        answer: str,
        sources: list[dict],
        evaluation: dict = None,
        latency_ms: int = 0,
        metadata: dict = None,
    ):
        """Track a complete RAG pipeline execution."""
        if not self.enabled or not self.client:
            return

        try:
            trace = self.client.trace(
                name="rag_pipeline",
                input=query,
                output=answer,
                metadata={
                    "source_count": len(sources),
                    "latency_ms": latency_ms,
                    "evaluation": evaluation,
                    **(metadata or {}),
                },
            )
            return trace
        except Exception as e:
            logger.debug(f"Failed to track RAG pipeline: {e}")

    def get_usage_stats(self, period_hours: int = 24) -> dict[str, Any]:
        """Get usage statistics from LangFuse."""
        if not self.enabled or not self.client:
            return {"enabled": False}

        try:
            # LangFuse SDK doesn't have a direct stats API
            # This would typically be done via the LangFuse API
            return {
                "enabled": True,
                "message": "Check LangFuse dashboard for detailed stats",
            }
        except Exception as e:
            logger.debug(f"Failed to get usage stats: {e}")
            return {"enabled": True, "error": str(e)}

    def flush(self):
        """Flush pending traces to LangFuse."""
        if self.enabled and self.client:
            try:
                self.client.flush()
            except Exception as e:
                logger.debug(f"Failed to flush traces: {e}")


# Global instance
observability = ObservabilityManager()


# Decorator for tracing functions
def traced(name: str = None, metadata: dict = None):
    """
    Decorator to trace a function.
    Usage:
        @traced("my_function", metadata={"key": "value"})
        async def my_function(arg1, arg2):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            trace_name = name or func.__name__
            with observability.create_trace(trace_name, metadata=metadata) as trace:
                try:
                    result = await func(*args, **kwargs)
                    if trace:
                        trace.add_event("completion", output_data=result)
                    return result
                except Exception as e:
                    if trace:
                        trace.add_event("error", metadata={"error": str(e)})
                    raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            trace_name = name or func.__name__
            with observability.create_trace(trace_name, metadata=metadata) as trace:
                try:
                    result = func(*args, **kwargs)
                    if trace:
                        trace.add_event("completion", output_data=result)
                    return result
                except Exception as e:
                    if trace:
                        trace.add_event("error", metadata={"error": str(e)})
                    raise

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


# Convenience functions
def track_llm(model: str, prompt: str, completion: str, tokens_in: int = 0, tokens_out: int = 0, latency_ms: int = 0):
    """Track an LLM call."""
    return observability.track_llm_call(model, prompt, completion, tokens_in, tokens_out, latency_ms)


def track_embedding(model: str, texts: list[str], latency_ms: int = 0):
    """Track an embedding call."""
    return observability.track_embedding(model, texts, latency_ms)


def track_retrieval(query: str, results: list[dict], latency_ms: int = 0, metadata: dict = None):
    """Track a retrieval operation."""
    return observability.track_retrieval(query, results, latency_ms, metadata)


def track_rag(
    query: str,
    answer: str,
    sources: list[dict],
    evaluation: dict = None,
    latency_ms: int = 0,
    metadata: dict = None,
):
    """Track a RAG pipeline execution."""
    return observability.track_rag_pipeline(query, answer, sources, evaluation, latency_ms, metadata)
