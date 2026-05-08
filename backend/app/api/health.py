"""
Health check API for MindPilot.

Provides endpoints for liveness, readiness, and detailed health checks
for Kubernetes probes and monitoring systems.
"""
import time
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Response
from pydantic import BaseModel

from app.config import settings
from app.rag.vector_store import vector_store
from app.storage.database import get_db_session
from app.storage.redis_client import redis_client

router = APIRouter(prefix="/health", tags=["Health"])

# Track startup time
START_TIME = time.time()


class ComponentHealth(BaseModel):
    """Health status of a single component."""
    status: str  # "healthy", "unhealthy", "degraded"
    latency_ms: float | None = None
    message: str | None = None
    details: dict[str, Any] | None = None


class HealthCheckResponse(BaseModel):
    """Full health check response."""
    status: str  # "healthy", "unhealthy", "degraded"
    version: str
    uptime_seconds: float
    timestamp: str
    components: dict[str, ComponentHealth]


class LivenessResponse(BaseModel):
    """Simple liveness check response."""
    status: str = "alive"
    timestamp: str


class ReadinessResponse(BaseModel):
    """Readiness check response."""
    status: str  # "ready", "not_ready"
    message: str | None = None


async def check_mysql() -> ComponentHealth:
    """Check MySQL database connection."""
    start = time.perf_counter()
    try:
        async with get_db_session() as db:
            from sqlalchemy import text
            await db.execute(text("SELECT 1"))
        latency = (time.perf_counter() - start) * 1000
        return ComponentHealth(
            status="healthy",
            latency_ms=round(latency, 2),
            message="MySQL connection successful"
        )
    except Exception as e:
        return ComponentHealth(
            status="unhealthy",
            message=f"MySQL connection failed: {str(e)}"
        )


async def check_redis() -> ComponentHealth:
    """Check Redis connection."""
    start = time.perf_counter()
    try:
        if redis_client._client is None:
            await redis_client.connect()
        await redis_client.client.ping()
        latency = (time.perf_counter() - start) * 1000
        return ComponentHealth(
            status="healthy",
            latency_ms=round(latency, 2),
            message="Redis connection successful"
        )
    except Exception as e:
        return ComponentHealth(
            status="unhealthy",
            message=f"Redis connection failed: {str(e)}"
        )


def check_vector_store() -> ComponentHealth:
    """Check Vector store (Milvus/FAISS) connection."""
    start = time.perf_counter()
    try:
        if settings.VECTOR_STORE == "milvus":
            if not vector_store.is_connected:
                vector_store.connect()
            stats = vector_store.get_stats()
            latency = (time.perf_counter() - start) * 1000
            if stats.get("connected"):
                return ComponentHealth(
                    status="healthy",
                    latency_ms=round(latency, 2),
                    message=f"Milvus connection successful ({stats.get('total_vectors', 0)} vectors)"
                )
            else:
                return ComponentHealth(status="unhealthy", message="Milvus not connected")
        else:
            # FAISS is local, always healthy
            latency = (time.perf_counter() - start) * 1000
            return ComponentHealth(
                status="healthy",
                latency_ms=round(latency, 2),
                message="FAISS (local) ready"
            )
    except Exception as e:
        return ComponentHealth(
            status="unhealthy",
            message=f"Vector store error: {str(e)}"
        )


async def check_embedding_service() -> ComponentHealth:
    """Check embedding service availability."""
    start = time.perf_counter()
    try:
        from app.rag.embedder import embedder
        # Test with a small input
        result = await embedder.embed_query("test")
        latency = (time.perf_counter() - start) * 1000
        return ComponentHealth(
            status="healthy",
            latency_ms=round(latency, 2),
            message=f"Embedding service OK (dim={len(result)})"
        )
    except Exception as e:
        return ComponentHealth(
            status="degraded",
            message=f"Embedding service issue: {str(e)}"
        )


def get_version() -> str:
    """Get application version."""
    import os
    return os.getenv("APP_VERSION", "0.1.0")


@router.get("", response_model=LivenessResponse)
async def health_check():
    """Simple health check endpoint."""
    return LivenessResponse(timestamp=datetime.now(UTC).isoformat())


@router.get("/live", response_model=LivenessResponse)
async def liveness():
    """Kubernetes liveness probe endpoint."""
    return LivenessResponse(timestamp=datetime.now(UTC).isoformat())


@router.get("/ready")
async def readiness(response: Response):
    """Kubernetes readiness probe endpoint."""
    # Check critical components
    mysql_health = await check_mysql()
    redis_health = await check_redis()

    critical_healthy = (
        mysql_health.status == "healthy" and
        redis_health.status == "healthy"
    )

    if critical_healthy:
        return ReadinessResponse(status="ready")
    else:
        response.status_code = 503
        return ReadinessResponse(
            status="not_ready",
            message="Critical components unhealthy"
        )


@router.get("/detailed", response_model=HealthCheckResponse)
async def detailed_health(response: Response):
    """Detailed health check endpoint."""
    # Run all checks
    mysql_health = await check_mysql()
    redis_health = await check_redis()
    vector_health = check_vector_store()
    embedding_health = await check_embedding_service()

    components = {
        "mysql": mysql_health,
        "redis": redis_health,
        "vector_store": vector_health,
        "embedding": embedding_health,
    }

    # Determine overall status
    statuses = [c.status for c in components.values()]
    if all(s == "healthy" for s in statuses):
        overall_status = "healthy"
    elif any(s == "unhealthy" for s in statuses):
        overall_status = "unhealthy"
        response.status_code = 503
    else:
        overall_status = "degraded"

    return HealthCheckResponse(
        status=overall_status,
        version=get_version(),
        uptime_seconds=round(time.time() - START_TIME, 2),
        timestamp=datetime.now(UTC).isoformat(),
        components=components
    )


@router.get("/metrics")
async def metrics_endpoint():
    """Prometheus metrics endpoint."""
    from app.core.metrics import get_metrics
    return Response(
        content=get_metrics(),
        media_type="text/plain; version=0.0.4; charset=utf-8"
    )


@router.get("/startup")
async def startup_check():
    """Startup probe for Kubernetes."""
    return {"status": "started", "timestamp": datetime.now(UTC).isoformat()}
