"""
MindPilot API - Multi-modal intelligent knowledge retrieval system.
"""
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.api import admin, analytics, auth, branches, chat, document, feishu, health, highlight, image, knowledge, workflow
from app.config import settings

# Setup structured logging
from app.core import (
    MetricsMiddleware,
    MindPilotException,
    RateLimitMiddleware,
    ValidationException,
    get_logger,
    get_request_id,
    set_request_id,
    set_user_id,
    setup_logging,
)
from app.core.rate_limit import RateLimitConfig
from app.storage import close_db, init_db
from app.storage.redis_client import redis_client

setup_logging(
    level="DEBUG" if settings.DEBUG else "INFO",
    json_format=not settings.DEBUG,  # JSON format in production
)
logger = get_logger(__name__)


class RequestTrackingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for request tracking and logging.

    - Generates unique request ID for each request
    - Logs request/response details
    - Tracks timing for metrics
    """

    async def dispatch(self, request: Request, call_next):
        # Generate request ID
        request_id = str(uuid.uuid4())[:8]
        set_request_id(request_id)

        # Extract user from JWT token if available (do not trust X-User-ID header)
        try:
            from app.auth import auth_handler
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
                token_data = auth_handler.verify_token(token)
                if token_data.user_id:
                    set_user_id(token_data.user_id)
        except Exception:
            pass

        # Log incoming request
        logger.info(
            f"Request started: {request.method} {request.url.path}",
            extra={
                "http": {
                    "method": request.method,
                    "path": request.url.path,
                    "query": str(request.query_params),
                }
            }
        )

        # Process request
        start_time = time.perf_counter()
        try:
            response = await call_next(request)
            latency_ms = (time.perf_counter() - start_time) * 1000

            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id

            # Log response
            logger.info(
                f"Request completed: {request.method} {request.url.path} - {response.status_code}",
                extra={
                    "http": {
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": response.status_code,
                        "latency_ms": round(latency_ms, 2),
                    }
                }
            )

            return response

        except Exception as exc:
            latency_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                f"Request failed: {request.method} {request.url.path}",
                extra={
                    "http": {
                        "method": request.method,
                        "path": request.url.path,
                        "latency_ms": round(latency_ms, 2),
                    },
                    "error": str(exc),
                }
            )
            raise


class ExceptionHandlerMiddleware(BaseHTTPMiddleware):
    """
    Middleware for unified exception handling.

    Catches all MindPilotException and converts them to proper JSON responses.
    """

    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except ValidationException as exc:
            logger.warning(
                f"Validation error: {exc.message}",
                extra={"details": exc.details}
            )
            return JSONResponse(
                status_code=400,
                content=exc.to_dict(),
                headers={"X-Request-ID": get_request_id() or "unknown"},
            )
        except MindPilotException as exc:
            logger.error(
                f"MindPilotException: [{exc.error_code}] {exc.message}",
                extra={
                    "error_code": exc.error_code,
                    "details": exc.details,
                }
            )
            return JSONResponse(
                status_code=exc.http_status,
                content=exc.to_dict(),
                headers={"X-Request-ID": get_request_id() or "unknown"},
            )
        except Exception as exc:
            logger.exception(f"Unexpected error: {exc}")
            return JSONResponse(
                status_code=500,
                content={
                    "error": True,
                    "error_code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred",
                    "request_id": get_request_id(),
                },
                headers={"X-Request-ID": get_request_id() or "unknown"},
            )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"Debug mode: {settings.DEBUG}")
    logger.info(f"Environment: {settings.ENVIRONMENT}")

    # Initialize connections
    try:
        await init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise

    try:
        await redis_client.connect()
        logger.info("Redis connected successfully")
    except Exception as e:
        logger.warning(f"Redis connection failed: {e} - continuing without cache")

    logger.info(f"{settings.APP_NAME} is ready to serve requests")
    yield

    # Cleanup
    logger.info(f"Shutting down {settings.APP_NAME}")
    await redis_client.disconnect()
    await close_db()
    logger.info("Cleanup completed")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Multi-modal intelligent knowledge retrieval and multi-platform collaboration system",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add custom middleware (order matters - last added is first executed)
app.add_middleware(RateLimitMiddleware, config=RateLimitConfig())
app.add_middleware(MetricsMiddleware)
app.add_middleware(ExceptionHandlerMiddleware)
app.add_middleware(RequestTrackingMiddleware)


# Root endpoints
@app.get("/", tags=["System"])
async def root():
    """Root endpoint."""
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "docs": "/docs",
        "health": "/health",
        "metrics": "/health/metrics",
    }


# Include routers
app.include_router(health.router, tags=["Health"])
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(document.router, prefix="/api/document", tags=["Document"])
app.include_router(knowledge.router, prefix="/api/knowledge", tags=["Knowledge"])
app.include_router(workflow.router, prefix="/api/workflow", tags=["Workflow"])
app.include_router(feishu.router, prefix="/api/feishu", tags=["Feishu Bot"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])
app.include_router(image.router, prefix="/api/image", tags=["Image"])
app.include_router(branches.router, prefix="/api/branches", tags=["Branches"])
app.include_router(highlight.router, prefix="/api/highlight", tags=["Highlight"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["Analytics"])


# Global exception handlers (fallback for middleware)
@app.exception_handler(MindPilotException)
async def mindpilot_exception_handler(request: Request, exc: MindPilotException):
    """Handle MindPilot exceptions."""
    return JSONResponse(
        status_code=exc.http_status,
        content=exc.to_dict(),
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    logger.exception(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "error_code": "INTERNAL_ERROR",
            "message": "An unexpected error occurred",
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="debug" if settings.DEBUG else "info",
    )
