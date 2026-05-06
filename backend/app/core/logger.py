"""
Structured logging system for MindPilot.

Provides JSON-formatted logs with request tracking, correlation IDs,
and configurable output formats for production observability.
"""
import json
import logging
import sys
import uuid
from contextvars import ContextVar
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any

# Context variables for request tracking
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
user_id_var: ContextVar[str | None] = ContextVar("user_id", default=None)
session_id_var: ContextVar[str | None] = ContextVar("session_id", default=None)


def get_request_id() -> str | None:
    """Get current request ID from context."""
    return request_id_var.get()


def set_request_id(request_id: str | None = None) -> str:
    """Set request ID in context, generate if not provided."""
    rid = request_id or str(uuid.uuid4())[:8]
    request_id_var.set(rid)
    return rid


def get_user_id() -> str | None:
    """Get current user ID from context."""
    return user_id_var.get()


def set_user_id(user_id: str | None) -> None:
    """Set user ID in context."""
    user_id_var.set(user_id)


def get_session_id() -> str | None:
    """Get current session ID from context."""
    return session_id_var.get()


def set_session_id(session_id: str | None) -> None:
    """Set session ID in context."""
    session_id_var.set(session_id)


class JSONFormatter(logging.Formatter):
    """
    JSON formatter for structured logging.

    Outputs logs as JSON objects with consistent fields:
    - timestamp: ISO 8601 timestamp
    - level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    - logger: Logger name
    - message: Log message
    - request_id: Request correlation ID (if available)
    - user_id: User ID (if available)
    - session_id: Session ID (if available)
    - extra: Additional context fields
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        # Base log entry
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add context from ContextVar
        if request_id := get_request_id():
            log_entry["request_id"] = request_id
        if user_id := get_user_id():
            log_entry["user_id"] = user_id
        if session_id := get_session_id():
            log_entry["session_id"] = session_id

        # Add location info for errors
        if record.levelno >= logging.ERROR:
            log_entry["file"] = f"{record.filename}:{record.lineno}"
            log_entry["function"] = record.funcName

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Add extra fields
        if hasattr(record, "extra") and record.extra:
            log_entry["extra"] = record.extra

        # Add any additional attributes passed via extra param
        standard_attrs = {
            "name", "msg", "args", "created", "filename", "funcName",
            "levelname", "levelno", "lineno", "module", "msecs",
            "pathname", "process", "processName", "relativeCreated",
            "stack_info", "exc_info", "exc_text", "thread", "threadName",
            "message", "asctime", "extra"
        }
        for key, value in record.__dict__.items():
            if key not in standard_attrs:
                log_entry[key] = value

        return json.dumps(log_entry, ensure_ascii=False, default=str)


class HumanFormatter(logging.Formatter):
    """
    Human-readable formatter for development.

    Format: [timestamp] LEVEL name | request_id | message
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format log record for human reading."""
        # Build prefix
        parts = [
            datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S"),
            record.levelname.ljust(8),
            record.name,
        ]

        # Add request ID if available
        if request_id := get_request_id():
            parts.append(f"[{request_id}]")

        # Build message
        message = " | ".join(parts) + f" | {record.getMessage()}"

        # Add exception if present
        if record.exc_info:
            message += f"\n{self.formatException(record.exc_info)}"

        return message


class LoggerAdapter(logging.LoggerAdapter):
    """
    Logger adapter that adds extra context to log records.

    Usage:
        logger = get_logger("module")
        logger.info("Message", key="value")              # kwargs → extra
        logger.info("Message", extra={"key": "value"})   # explicit extra
        logger.bind(operation="query").info("Message")   # bound context
    """

    def __init__(self, logger: logging.Logger, extra: dict[str, Any] | None = None):
        super().__init__(logger, extra or {})

    def process(self, msg: str, kwargs: dict[str, Any]) -> tuple:
        """Process logging call: merge all keyword args into extra."""
        # Collect extra from explicit extra=, plus all other kwargs
        explicit_extra = kwargs.pop("extra", {})
        # All remaining kwargs become structured fields
        merged_extra = {**self.extra, **explicit_extra, **kwargs}
        # Return clean kwargs with only extra set
        return msg, {"extra": merged_extra}

    def bind(self, **kwargs: Any) -> "LoggerAdapter":
        """Create a new adapter with additional context."""
        return LoggerAdapter(self.logger, {**self.extra, **kwargs})


@lru_cache(maxsize=128)
def get_logger(name: str) -> LoggerAdapter:
    """
    Get a logger instance with JSON formatting.

    Args:
        name: Logger name (typically __name__)

    Returns:
        LoggerAdapter instance with structured logging support
    """
    logger = logging.getLogger(name)
    return LoggerAdapter(logger)


def setup_logging(
    level: str = "INFO",
    json_format: bool = True,
    log_file: str | None = None,
) -> None:
    """
    Configure the root logger for MindPilot.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_format: Use JSON format (True) or human-readable (False)
        log_file: Optional file path for log output
    """
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove existing handlers
    root_logger.handlers.clear()

    # Create formatter
    formatter = JSONFormatter() if json_format else HumanFormatter()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler (optional)
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    # Suppress noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("pymilvus").setLevel(logging.WARNING)
    logging.getLogger("paddleocr").setLevel(logging.WARNING)


class RequestContext:
    """
    Context manager for request-scoped logging context.

    Usage:
        with RequestContext(user_id="user123"):
            logger.info("Processing request")  # Will include user_id
    """

    def __init__(
        self,
        request_id: str | None = None,
        user_id: str | None = None,
        session_id: str | None = None,
    ):
        self.request_id = request_id
        self.user_id = user_id
        self.session_id = session_id
        self._prev_request_id: str | None = None
        self._prev_user_id: str | None = None
        self._prev_session_id: str | None = None

    def __enter__(self) -> "RequestContext":
        """Set context variables."""
        self._prev_request_id = get_request_id()
        self._prev_user_id = get_user_id()
        self._prev_session_id = get_session_id()

        if self.request_id:
            set_request_id(self.request_id)
        if self.user_id:
            set_user_id(self.user_id)
        if self.session_id:
            set_session_id(self.session_id)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Restore previous context."""
        request_id_var.set(self._prev_request_id)
        user_id_var.set(self._prev_user_id)
        session_id_var.set(self._prev_session_id)


# Convenience functions for common log patterns
def log_request(
    logger: logging.Logger,
    method: str,
    path: str,
    status_code: int,
    latency_ms: float,
    **kwargs: Any
) -> None:
    """Log an HTTP request."""
    logger.info(
        f"{method} {path} - {status_code}",
        extra={
            "http": {
                "method": method,
                "path": path,
                "status_code": status_code,
                "latency_ms": latency_ms,
            },
            **kwargs
        }
    )


def log_rag_operation(
    logger: logging.Logger,
    operation: str,
    knowledge_base: str,
    success: bool,
    latency_ms: float,
    **kwargs: Any
) -> None:
    """Log a RAG operation."""
    level = logging.INFO if success else logging.WARNING
    logger.log(
        level,
        f"RAG {operation} - {'success' if success else 'failed'}",
        extra={
            "rag": {
                "operation": operation,
                "knowledge_base": knowledge_base,
                "success": success,
                "latency_ms": latency_ms,
            },
            **kwargs
        }
    )
