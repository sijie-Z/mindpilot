"""
Tests for structured logging system.
"""
import json
import logging
import sys


class TestJSONFormatter:
    """Tests for JSON log formatter."""

    def test_formatter_outputs_json(self):
        """Test formatter produces valid JSON."""
        from app.core.logger import JSONFormatter

        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="test.py",
            lineno=42, msg="Test message", args=(), exc_info=None
        )

        output = formatter.format(record)
        data = json.loads(output)

        assert data["level"] == "INFO"
        assert data["message"] == "Test message"
        assert data["logger"] == "test"
        assert "timestamp" in data

    def test_formatter_includes_error_location(self):
        """Test error logs include file and function info."""
        from app.core.logger import JSONFormatter

        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test", level=logging.ERROR, pathname="api.py",
            lineno=100, msg="Something broke", args=(), exc_info=None
        )
        record.funcName = "handle_request"

        output = formatter.format(record)
        data = json.loads(output)

        assert data["file"] == "api.py:100"
        assert data["function"] == "handle_request"

    def test_formatter_includes_exception(self):
        """Test formatter includes exception info when present."""
        from app.core.logger import JSONFormatter

        formatter = JSONFormatter()
        try:
            raise ValueError("test error")
        except ValueError:
            record = logging.LogRecord(
                name="test", level=logging.ERROR, pathname="test.py",
                lineno=1, msg="Error occurred", args=(), exc_info=sys.exc_info()
            )

        output = formatter.format(record)
        data = json.loads(output)

        assert "exception" in data
        assert "ValueError" in data["exception"]

    def test_formatter_includes_context(self):
        """Test formatter includes request/user/session context."""
        from app.core.logger import JSONFormatter, set_request_id, set_session_id, set_user_id

        set_request_id("req-123")
        set_user_id("user-456")
        set_session_id("sess-789")

        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="test.py",
            lineno=1, msg="Contextual log", args=(), exc_info=None
        )

        output = formatter.format(record)
        data = json.loads(output)

        assert data["request_id"] == "req-123"
        assert data["user_id"] == "user-456"
        assert data["session_id"] == "sess-789"


class TestHumanFormatter:
    """Tests for human-readable log formatter."""

    def test_formatter_basic(self):
        """Test human formatter produces readable output."""
        from app.core.logger import HumanFormatter

        formatter = HumanFormatter()
        record = logging.LogRecord(
            name="app.api", level=logging.INFO, pathname="api.py",
            lineno=42, msg="Request processed", args=(), exc_info=None
        )

        output = formatter.format(record)
        assert "INFO" in output
        assert "app.api" in output
        assert "Request processed" in output


class TestLoggerAdapter:
    """Tests for LoggerAdapter with structured context."""

    def test_get_logger_returns_adapter(self):
        """Test get_logger returns LoggerAdapter."""
        from app.core.logger import LoggerAdapter, get_logger

        logger = get_logger("test_module")
        assert isinstance(logger, LoggerAdapter)

    def test_logger_adapter_bind(self):
        """Test binding additional context."""
        from app.core.logger import get_logger

        logger = get_logger("test_module")
        bound = logger.bind(operation="test_op", user_id="user1")

        assert bound.extra["operation"] == "test_op"
        assert bound.extra["user_id"] == "user1"

    def test_logger_adapter_process(self):
        """Test adapter merges kwargs into extra."""
        from app.core.logger import get_logger

        logger = get_logger("test_module")
        msg, kwargs = logger.process("Test message", {"key": "value"})

        assert kwargs["extra"]["key"] == "value"


class TestRequestContext:
    """Tests for request context variables."""

    def test_set_and_get_request_id(self):
        """Test setting and getting request ID."""
        from app.core.logger import get_request_id, set_request_id

        rid = set_request_id("custom-id")
        assert rid == "custom-id"
        assert get_request_id() == "custom-id"

    def test_generate_request_id(self):
        """Test auto-generated request ID."""
        from app.core.logger import set_request_id

        rid = set_request_id()
        assert rid is not None
        assert len(rid) == 8

    def test_user_id_context(self):
        """Test user ID context variable."""
        from app.core.logger import get_user_id, set_user_id

        set_user_id("user-999")
        assert get_user_id() == "user-999"

    def test_session_id_context(self):
        """Test session ID context variable."""
        from app.core.logger import get_session_id, set_session_id

        set_session_id("session-abc")
        assert get_session_id() == "session-abc"

    def test_request_context_manager(self):
        """Test RequestContext restores previous values."""
        from app.core.logger import (
            RequestContext,
            get_request_id,
            get_session_id,
            get_user_id,
            set_request_id,
            set_session_id,
            set_user_id,
        )

        set_request_id("outer")
        set_user_id("outer-user")
        set_session_id("outer-session")

        with RequestContext(request_id="inner", user_id="inner-user"):
            assert get_request_id() == "inner"
            assert get_user_id() == "inner-user"

        # Should restore outer values
        assert get_request_id() == "outer"
        assert get_user_id() == "outer-user"
        assert get_session_id() == "outer-session"


class TestLogFunctions:
    """Tests for convenience logging functions."""

    def test_log_request(self, caplog):
        """Test HTTP request logging helper."""
        from app.core.logger import get_logger, log_request

        logger = get_logger("test.http")
        with caplog.at_level(logging.INFO):
            log_request(logger.logger, "GET", "/api/health", 200, 15.5)

        assert "GET" in caplog.text
        assert "/api/health" in caplog.text

    def test_log_rag_operation(self, caplog):
        """Test RAG operation logging helper."""
        from app.core.logger import get_logger, log_rag_operation

        logger = get_logger("test.rag")
        with caplog.at_level(logging.INFO):
            log_rag_operation(logger.logger, "search", "kb_main", True, 250.0)

        assert "search" in caplog.text
        assert "success" in caplog.text


class TestSetupLogging:
    """Tests for logging setup."""

    def test_setup_logging_console(self):
        """Test setup_logging adds console handler."""
        from app.core.logger import setup_logging

        setup_logging(level="DEBUG", json_format=False)

        root = logging.getLogger()
        assert len(root.handlers) >= 1
        assert root.level == logging.DEBUG

    def test_setup_logging_json(self):
        """Test setup_logging with JSON format."""
        from app.core.logger import setup_logging

        setup_logging(level="INFO", json_format=True)

        root = logging.getLogger()
        assert len(root.handlers) >= 1
        assert root.level == logging.INFO
