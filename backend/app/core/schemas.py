"""
Enhanced Pydantic schemas for MindPilot API validation.

Provides strict validation models for all API endpoints,
ensuring input correctness and providing clear error messages.
"""
import re
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class MessageRole(str, Enum):
    """Chat message role."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class KnowledgeBaseStatus(str, Enum):
    """Knowledge base status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    PROCESSING = "processing"
    ERROR = "error"


class DocumentStatus(str, Enum):
    """Document processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DocumentCategory(str, Enum):
    """Document category for knowledge base."""
    MANUAL = "manual"
    FAQ = "faq"
    POLICY = "policy"
    TECHNICAL = "technical"
    OTHER = "other"


class ChunkStrategy(str, Enum):
    """Document chunking strategy."""
    FIXED_SIZE = "fixed_size"
    SEMANTIC = "semantic"
    SENTENCE = "sentence"
    PARAGRAPH = "paragraph"


# Base models with common configuration
class BaseRequestModel(BaseModel):
    """Base model for API requests."""
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )


class BaseResponseModel(BaseModel):
    """Base model for API responses."""
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )


# ============== Auth Schemas ==============

class UserLoginRequest(BaseRequestModel):
    """Login request schema."""
    username: str = Field(..., min_length=3, max_length=50, description="Username")
    password: str = Field(..., min_length=6, max_length=100, description="Password")


class UserRegisterRequest(BaseRequestModel):
    """Registration request schema."""
    username: str = Field(..., min_length=3, max_length=50, description="Username")
    password: str = Field(..., min_length=6, max_length=100, description="Password")
    email: str = Field(default="", max_length=100, description="Email address")

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        """Validate username format."""
        if not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError("Username can only contain letters, numbers, underscores and hyphens")
        return v

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        """Validate email format if provided."""
        if v and not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", v):
            raise ValueError("Invalid email format")
        return v


class TokenResponse(BaseResponseModel):
    """Token response schema."""
    access_token: str
    token_type: str = "bearer"
    user_id: str
    username: str
    expires_in: int | None = None


class UserResponse(BaseResponseModel):
    """User info response schema."""
    id: str
    username: str
    email: str
    role: str


# ============== Chat Schemas ==============

class ChatMessage(BaseModel):
    """Chat message schema."""
    role: MessageRole
    content: str = Field(..., min_length=1, max_length=50000)
    timestamp: datetime | None = None


class ChatRequest(BaseRequestModel):
    """Chat request schema."""
    message: str = Field(
        ...,
        min_length=1,
        max_length=50000,
        description="User message"
    )
    knowledge_base_ids: list[str] | None = Field(
        default=None,
        max_length=10,
        description="Knowledge base IDs to search"
    )
    session_id: str | None = Field(
        default=None,
        max_length=100,
        description="Session ID for conversation continuity"
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Number of documents to retrieve"
    )
    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="LLM temperature"
    )
    stream: bool = Field(
        default=False,
        description="Whether to stream response"
    )

    @field_validator("message")
    @classmethod
    def sanitize_message(cls, v: str) -> str:
        """Sanitize user message."""
        # Remove potential XSS (basic sanitization)
        v = v.replace("<script>", "&lt;script&gt;").replace("</script>", "&lt;/script&gt;")
        return v.strip()

    @field_validator("knowledge_base_ids")
    @classmethod
    def validate_knowledge_base_ids(cls, v: list[str] | None) -> list[str] | None:
        """Validate knowledge base IDs."""
        if v:
            seen = set()
            for kid in v:
                if kid in seen:
                    raise ValueError(f"Duplicate knowledge base ID: {kid}")
                seen.add(kid)
        return v


class ChatResponse(BaseResponseModel):
    """Chat response schema."""
    response: str
    session_id: str
    sources: list[dict[str, Any]] | None = None
    latency_ms: float
    retrieval_count: int
    llm_model: str


class StreamChunk(BaseResponseModel):
    """Streaming response chunk."""
    content: str
    done: bool = False
    session_id: str


# ============== Knowledge Base Schemas ==============

class KnowledgeBaseCreate(BaseRequestModel):
    """Create knowledge base request."""
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Knowledge base name"
    )
    description: str = Field(
        default="",
        max_length=500,
        description="Knowledge base description"
    )
    embedding_model: str = Field(
        default="text-embedding-3-small",
        max_length=100,
        description="Embedding model to use"
    )
    chunk_strategy: ChunkStrategy = Field(
        default=ChunkStrategy.FIXED_SIZE,
        description="Chunking strategy"
    )
    chunk_size: int = Field(
        default=512,
        ge=100,
        le=2000,
        description="Chunk size in tokens"
    )
    chunk_overlap: int = Field(
        default=50,
        ge=0,
        le=500,
        description="Chunk overlap in tokens"
    )

    @model_validator(mode="after")
    def validate_chunk_params(self) -> "KnowledgeBaseCreate":
        """Validate chunk size and overlap relationship."""
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("Chunk overlap must be less than chunk size")
        return self


class KnowledgeBaseUpdate(BaseRequestModel):
    """Update knowledge base request."""
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    status: KnowledgeBaseStatus | None = None
    chunk_strategy: ChunkStrategy | None = None
    chunk_size: int | None = Field(default=None, ge=100, le=2000)
    chunk_overlap: int | None = Field(default=None, ge=0, le=500)


class KnowledgeBaseResponse(BaseResponseModel):
    """Knowledge base response schema."""
    id: str
    name: str
    description: str
    status: str
    embedding_model: str
    chunk_strategy: str
    chunk_size: int
    chunk_overlap: int
    document_count: int
    chunk_count: int
    created_at: datetime
    updated_at: datetime | None = None


class KnowledgeBaseListResponse(BaseResponseModel):
    """Knowledge base list response."""
    items: list[KnowledgeBaseResponse]
    total: int
    page: int
    page_size: int


# ============== Document Schemas ==============

class DocumentUploadRequest(BaseRequestModel):
    """Document upload request (metadata only, file upload handled separately)."""
    knowledge_base_id: str = Field(..., min_length=1, description="Target knowledge base ID")
    category: DocumentCategory = Field(
        default=DocumentCategory.OTHER,
        description="Document category"
    )
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Additional metadata"
    )


class DocumentResponse(BaseResponseModel):
    """Document response schema."""
    id: str
    name: str
    knowledge_base_id: str
    category: str
    status: str
    size_bytes: int
    chunk_count: int
    created_at: datetime
    processed_at: datetime | None = None
    error_message: str | None = None


class DocumentListResponse(BaseResponseModel):
    """Document list response."""
    items: list[DocumentResponse]
    total: int
    page: int
    page_size: int


class ChunkSearchRequest(BaseRequestModel):
    """Search chunks request."""
    knowledge_base_ids: list[str] | None = Field(
        default=None,
        max_length=10,
        description="Knowledge base IDs to search"
    )
    query: str = Field(..., min_length=1, max_length=1000, description="Search query")
    top_k: int = Field(default=10, ge=1, le=100, description="Number of results")
    min_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Minimum relevance score")


class ChunkResponse(BaseResponseModel):
    """Chunk response schema."""
    id: str
    document_id: str
    document_name: str
    knowledge_base_id: str
    content: str
    score: float
    metadata: dict[str, Any] | None = None


# ============== Admin Schemas ==============

class RetrievalConfig(BaseRequestModel):
    """Retrieval configuration."""
    vector_weight: float = Field(default=0.7, ge=0.0, le=1.0)
    bm25_weight: float = Field(default=0.3, ge=0.0, le=1.0)
    top_k: int = Field(default=10, ge=1, le=100)
    rerank_enabled: bool = Field(default=True)
    rerank_top_n: int = Field(default=5, ge=1, le=20)
    min_relevance_score: float = Field(default=0.3, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_weights(self) -> "RetrievalConfig":
        """Validate weight configuration."""
        total = self.vector_weight + self.bm25_weight
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"vector_weight + bm25_weight must equal 1.0, got {total}")
        return self


class SystemStatsResponse(BaseResponseModel):
    """System statistics response."""
    total_queries: int
    avg_latency: float
    token_usage: str
    avg_score: float
    active_sessions: int
    total_knowledge_bases: int
    total_documents: int
    total_chunks: int


class HealthCheckResponse(BaseResponseModel):
    """Health check response."""
    status: str
    version: str
    components: dict[str, Any]
    uptime_seconds: float


# ============== Error Schemas ==============

class ErrorResponse(BaseResponseModel):
    """API error response schema."""
    error: bool = True
    error_code: str
    message: str
    details: dict[str, Any] | None = None


class ValidationErrorDetail(BaseResponseModel):
    """Validation error detail."""
    field: str
    message: str
    value: Any | None = None


class ValidationErrorResponse(BaseResponseModel):
    """Validation error response."""
    error: bool = True
    error_code: str = "VALIDATION_ERROR"
    message: str = "Validation failed"
    details: list[ValidationErrorDetail]
