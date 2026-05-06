"""
Unified exception hierarchy for MindPilot.

All custom exceptions inherit from MindPilotException,
providing consistent error codes, messages, and HTTP status codes.
"""
from enum import Enum
from typing import Any


class ErrorCode(str, Enum):
    """Error codes for MindPilot exceptions."""
    # General errors
    INTERNAL_ERROR = "INTERNAL_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"

    # LLM errors
    LLM_ERROR = "LLM_ERROR"
    LLM_TIMEOUT = "LLM_TIMEOUT"
    LLM_RATE_LIMIT = "LLM_RATE_LIMIT"

    # Embedding errors
    EMBEDDING_ERROR = "EMBEDDING_ERROR"
    EMBEDDING_TIMEOUT = "EMBEDDING_TIMEOUT"

    # Vector store errors
    VECTOR_STORE_ERROR = "VECTOR_STORE_ERROR"
    VECTOR_STORE_CONNECTION = "VECTOR_STORE_CONNECTION"
    VECTOR_STORE_NOT_FOUND = "VECTOR_STORE_NOT_FOUND"

    # Document processing errors
    DOCUMENT_ERROR = "DOCUMENT_ERROR"
    DOCUMENT_PARSE_ERROR = "DOCUMENT_PARSE_ERROR"
    DOCUMENT_TOO_LARGE = "DOCUMENT_TOO_LARGE"
    UNSUPPORTED_FORMAT = "UNSUPPORTED_FORMAT"

    # Retrieval errors
    RETRIEVAL_ERROR = "RETRIEVAL_ERROR"
    NO_RELEVANT_DOCS = "NO_RELEVANT_DOCS"

    # Database errors
    DATABASE_ERROR = "DATABASE_ERROR"
    DATABASE_CONNECTION = "DATABASE_CONNECTION"

    # Cache errors
    CACHE_ERROR = "CACHE_ERROR"
    CACHE_CONNECTION = "CACHE_CONNECTION"


class MindPilotException(Exception):
    """
    Base exception for all MindPilot errors.

    Attributes:
        error_code: Unique error code for categorization
        message: Human-readable error message
        details: Additional context about the error
        http_status: HTTP status code for API responses
    """

    error_code: str = ErrorCode.INTERNAL_ERROR
    http_status: int = 500

    def __init__(
        self,
        message: str,
        error_code: str | None = None,
        details: dict[str, Any] | None = None,
        http_status: int | None = None,
    ):
        self.message = message
        self.error_code = error_code or self.error_code
        self.details = details or {}
        self.http_status = http_status or self.http_status
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary for API response."""
        return {
            "error": True,
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
        }

    def __str__(self) -> str:
        code = self.error_code.value if isinstance(self.error_code, ErrorCode) else self.error_code
        return f"[{code}] {self.message}"


class LLMException(MindPilotException):
    """Exception for LLM-related errors."""
    error_code = ErrorCode.LLM_ERROR
    http_status = 502


class LLMTimeoutException(LLMException):
    """Exception for LLM timeout errors."""
    error_code = ErrorCode.LLM_TIMEOUT
    http_status = 504


class LLMRateLimitException(LLMException):
    """Exception for LLM rate limit errors."""
    error_code = ErrorCode.LLM_RATE_LIMIT
    http_status = 429


class EmbeddingException(MindPilotException):
    """Exception for embedding-related errors."""
    error_code = ErrorCode.EMBEDDING_ERROR
    http_status = 502


class EmbeddingTimeoutException(EmbeddingException):
    """Exception for embedding timeout errors."""
    error_code = ErrorCode.EMBEDDING_TIMEOUT
    http_status = 504


class VectorStoreException(MindPilotException):
    """Exception for vector store errors (Milvus/FAISS)."""
    error_code = ErrorCode.VECTOR_STORE_ERROR
    http_status = 502


class VectorStoreConnectionException(VectorStoreException):
    """Exception for vector store connection errors."""
    error_code = ErrorCode.VECTOR_STORE_CONNECTION
    http_status = 503


class DocumentProcessingException(MindPilotException):
    """Exception for document processing errors."""
    error_code = ErrorCode.DOCUMENT_ERROR
    http_status = 400


class DocumentParseException(DocumentProcessingException):
    """Exception for document parsing errors."""
    error_code = ErrorCode.DOCUMENT_PARSE_ERROR


class DocumentTooLargeException(DocumentProcessingException):
    """Exception when document exceeds size limit."""
    error_code = ErrorCode.DOCUMENT_TOO_LARGE
    http_status = 413


class UnsupportedFormatException(DocumentProcessingException):
    """Exception for unsupported file formats."""
    error_code = ErrorCode.UNSUPPORTED_FORMAT


class RetrievalException(MindPilotException):
    """Exception for retrieval-related errors."""
    error_code = ErrorCode.RETRIEVAL_ERROR
    http_status = 500


class NoRelevantDocsException(RetrievalException):
    """Exception when no relevant documents are found."""
    error_code = ErrorCode.NO_RELEVANT_DOCS
    http_status = 200  # Not an error, just no results

    def to_dict(self) -> dict[str, Any]:
        result = super().to_dict()
        result["no_results"] = True
        return result


class DatabaseException(MindPilotException):
    """Exception for database errors."""
    error_code = ErrorCode.DATABASE_ERROR
    http_status = 500


class DatabaseConnectionException(DatabaseException):
    """Exception for database connection errors."""
    error_code = ErrorCode.DATABASE_CONNECTION
    http_status = 503


class CacheException(MindPilotException):
    """Exception for cache (Redis) errors."""
    error_code = ErrorCode.CACHE_ERROR
    http_status = 500


class CacheConnectionException(CacheException):
    """Exception for cache connection errors."""
    error_code = ErrorCode.CACHE_CONNECTION
    http_status = 503


class ValidationException(MindPilotException):
    """Exception for input validation errors."""
    error_code = ErrorCode.VALIDATION_ERROR
    http_status = 400


class NotFoundException(MindPilotException):
    """Exception for resource not found errors."""
    error_code = ErrorCode.NOT_FOUND
    http_status = 404
