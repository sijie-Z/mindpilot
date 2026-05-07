"""
SQLAlchemy Models for MindPilot
"""
import uuid
from enum import Enum as PyEnum

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


def generate_uuid() -> str:
    return str(uuid.uuid4())


class DocumentStatus(PyEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class UserRole(PyEnum):
    USER = "user"
    ADMIN = "admin"


class User(Base):
    """User model."""
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.USER)
    api_key = Column(String(100), unique=True, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")


class Session(Base):
    """Chat session model."""
    __tablename__ = "sessions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(200), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="sessions")
    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan")


class Message(Base):
    """Chat message model."""
    __tablename__ = "messages"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    session_id = Column(String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # 'user', 'assistant', 'system'
    content = Column(Text, nullable=False)
    extra_data = Column("metadata", JSON, nullable=True)  # Store sources, tokens, etc.
    created_at = Column(DateTime, default=func.now(), index=True)

    # Relationships
    session = relationship("Session", back_populates="messages")


class Knowledge(Base):
    """Knowledge base model."""
    __tablename__ = "knowledges"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    is_public = Column(Boolean, default=False)
    doc_count = Column(Integer, default=0)
    chunk_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    documents = relationship("Document", back_populates="knowledge", cascade="all, delete-orphan")


class Document(Base):
    """Document model."""
    __tablename__ = "documents"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    knowledge_id = Column(String(36), ForeignKey("knowledges.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = Column(String(200), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_type = Column(String(20), nullable=True)  # pdf, docx, pptx, txt, md
    file_size = Column(Integer, nullable=True)
    status = Column(Enum(DocumentStatus), default=DocumentStatus.PENDING, index=True)
    chunks = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    knowledge = relationship("Knowledge", back_populates="documents")
    chunk_records = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")


class Chunk(Base):
    """Document chunk model for RAG."""
    __tablename__ = "chunks"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    doc_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    chunk_metadata = Column("metadata", JSON, nullable=True)  # page, source, heading, etc.
    embedding_id = Column(String(100), nullable=True)  # Milvus vector ID
    created_at = Column(DateTime, default=func.now())

    # Relationships
    document = relationship("Document", back_populates="chunk_records")

    # Full-text index for BM25 (ngram parser for Chinese)
    __table_args__ = (
        Index('content_fulltext', 'content', mysql_prefix='FULLTEXT', mysql_with_parser='ngram'),
    )


class Evaluation(Base):
    """RAGAS evaluation record."""
    __tablename__ = "evaluations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    session_id = Column(String(36), ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True, index=True)
    query = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    contexts = Column(JSON, nullable=True)  # Retrieved contexts
    metrics = Column(JSON, nullable=True)  # RAGAS metrics
    faithfulness = Column(Float, nullable=True)
    answer_relevance = Column(Float, nullable=True)
    context_precision = Column(Float, nullable=True)
    context_recall = Column(Float, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    tokens_used = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=func.now(), index=True)


class RetrievalConfig(Base):
    """Retrieval configuration for dynamic weight adjustment."""
    __tablename__ = "retrieval_configs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    knowledge_id = Column(String(36), ForeignKey("knowledges.id", ondelete="CASCADE"), nullable=True, index=True)
    vector_weight = Column(Float, default=0.7)
    bm25_weight = Column(Float, default=0.3)
    top_k = Column(Integer, default=10)
    rerank_enabled = Column(Boolean, default=True)
    self_rag_enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class SkillLog(Base):
    """Skill execution log."""
    __tablename__ = "skill_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    session_id = Column(String(36), ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True, index=True)
    skill_name = Column(String(50), nullable=False, index=True)
    input_params = Column(JSON, nullable=True)
    output_result = Column(JSON, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    success = Column(Boolean, default=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now(), index=True)
