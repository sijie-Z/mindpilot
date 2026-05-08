"""Initial schema — all core MindPilot tables.

Revision ID: 001
Revises: None
Create Date: 2026-04-28
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── users ──
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("username", sa.String(50), unique=True, nullable=False),
        sa.Column("email", sa.String(100), unique=True, nullable=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.Enum("user", "admin", name="userrole"), default="user"),
        sa.Column("api_key", sa.String(100), unique=True, nullable=True),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_users_username", "users", ["username"])

    # ── sessions ──
    op.create_table(
        "sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(200), nullable=True),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])

    # ── messages ──
    op.create_table(
        "messages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_messages_session_id", "messages", ["session_id"])
    op.create_index("ix_messages_created_at", "messages", ["created_at"])
    # Fulltext index on messages for conversation history search (Chinese support)
    op.execute(
        "CREATE FULLTEXT INDEX messages_content_fulltext ON messages (content) WITH PARSER ngram"
    )

    # ── knowledges ──
    op.create_table(
        "knowledges",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("is_public", sa.Boolean(), default=False),
        sa.Column("doc_count", sa.Integer(), default=0),
        sa.Column("chunk_count", sa.Integer(), default=0),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_knowledges_user_id", "knowledges", ["user_id"])

    # ── documents ──
    op.create_table(
        "documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("knowledge_id", sa.String(36), sa.ForeignKey("knowledges.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.String(200), nullable=False),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("file_type", sa.String(20), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("status", sa.Enum("pending", "processing", "done", "failed", name="documentstatus"), default="pending"),
        sa.Column("chunks", sa.Integer(), default=0),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_documents_knowledge_id", "documents", ["knowledge_id"])
    op.create_index("ix_documents_status", "documents", ["status"])

    # ── chunks (with ngram fulltext index for Chinese BM25) ──
    op.create_table(
        "chunks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("doc_id", sa.String(36), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("embedding_id", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_chunks_doc_id", "chunks", ["doc_id"])
    # MySQL fulltext index with ngram parser for Chinese tokenization
    op.execute(
        "CREATE FULLTEXT INDEX content_fulltext ON chunks (content) WITH PARSER ngram"
    )

    # ── evaluations ──
    op.create_table(
        "evaluations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("contexts", sa.JSON(), nullable=True),
        sa.Column("metrics", sa.JSON(), nullable=True),
        sa.Column("faithfulness", sa.Float(), nullable=True),
        sa.Column("answer_relevance", sa.Float(), nullable=True),
        sa.Column("context_precision", sa.Float(), nullable=True),
        sa.Column("context_recall", sa.Float(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("tokens_used", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_evaluations_session_id", "evaluations", ["session_id"])
    op.create_index("ix_evaluations_created_at", "evaluations", ["created_at"])

    # ── retrieval_configs ──
    op.create_table(
        "retrieval_configs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("knowledge_id", sa.String(36), sa.ForeignKey("knowledges.id", ondelete="CASCADE"), nullable=True),
        sa.Column("vector_weight", sa.Float(), default=0.7),
        sa.Column("bm25_weight", sa.Float(), default=0.3),
        sa.Column("top_k", sa.Integer(), default=10),
        sa.Column("rerank_enabled", sa.Boolean(), default=True),
        sa.Column("self_rag_enabled", sa.Boolean(), default=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_retrieval_configs_user_id", "retrieval_configs", ["user_id"])
    op.create_index("ix_retrieval_configs_knowledge_id", "retrieval_configs", ["knowledge_id"])

    # ── skill_logs ──
    op.create_table(
        "skill_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("skill_name", sa.String(50), nullable=False),
        sa.Column("input_params", sa.JSON(), nullable=True),
        sa.Column("output_result", sa.JSON(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("success", sa.Boolean(), default=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_skill_logs_session_id", "skill_logs", ["session_id"])
    op.create_index("ix_skill_logs_skill_name", "skill_logs", ["skill_name"])
    op.create_index("ix_skill_logs_created_at", "skill_logs", ["created_at"])


def downgrade() -> None:
    op.drop_table("skill_logs")
    op.drop_table("retrieval_configs")
    op.drop_table("evaluations")
    op.drop_table("chunks")
    op.drop_table("documents")
    op.drop_table("knowledges")
    op.drop_table("messages")
    op.drop_table("sessions")
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS userrole")
    op.execute("DROP TYPE IF EXISTS documentstatus")
