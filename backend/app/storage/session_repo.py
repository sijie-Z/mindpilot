"""
Session and message persistence for multi-turn conversations.
"""
import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text

from app.core.logger import get_logger
from app.storage.database import get_db_session

logger = get_logger(__name__)


class SessionRepository:
    """CRUD operations for chat sessions and messages."""

    async def create_session(
        self, session_id: str, user_id: str = "anonymous", title: str = ""
    ) -> str:
        """Create a new chat session. Returns session_id."""
        try:
            async with get_db_session() as db:
                await db.execute(
                    text(
                        "INSERT INTO sessions (id, user_id, title, is_active) "
                        "VALUES (:id, :user_id, :title, :is_active)"
                    ),
                    {
                        "id": session_id,
                        "user_id": user_id,
                        "title": title or "新对话",
                        "is_active": True,
                    },
                )
            logger.debug("Session created", session_id=session_id, user_id=user_id)
            return session_id
        except Exception as e:
            logger.error("Failed to create session", error=str(e))
            return session_id

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Add a message to a session."""
        try:
            async with get_db_session() as db:
                import uuid
                msg_id = str(uuid.uuid4())
                await db.execute(
                    text(
                        "INSERT INTO messages (id, session_id, role, content, metadata) "
                        "VALUES (:id, :session_id, :role, :content, :metadata)"
                    ),
                    {
                        "id": msg_id,
                        "session_id": session_id,
                        "role": role,
                        "content": content,
                        "metadata": json.dumps(metadata or {}, ensure_ascii=False),
                    },
                )
                # Update session timestamp
                await db.execute(
                    text("UPDATE sessions SET updated_at = :now WHERE id = :sid"),
                    {"now": datetime.now(UTC), "sid": session_id},
                )
        except Exception as e:
            logger.error("Failed to add message", error=str(e))

    async def get_session(self, session_id: str) -> dict[str, Any] | None:
        """Get session with messages."""
        try:
            async with get_db_session() as db:
                result = await db.execute(
                    text(
                        "SELECT id, user_id, title, is_active, created_at, updated_at "
                        "FROM sessions WHERE id = :sid"
                    ),
                    {"sid": session_id},
                )
                session_row = result.fetchone()
                if not session_row:
                    return None

                msgs_result = await db.execute(
                    text(
                        "SELECT role, content, metadata, created_at "
                        "FROM messages WHERE session_id = :sid ORDER BY created_at ASC"
                    ),
                    {"sid": session_id},
                )
                messages = [
                    {
                        "role": row[0],
                        "content": row[1],
                        "metadata": row[2] if isinstance(row[2], dict) else json.loads(row[2] or "{}"),
                        "created_at": str(row[3]),
                    }
                    for row in msgs_result.fetchall()
                ]

                return {
                    "id": session_row[0],
                    "user_id": session_row[1],
                    "title": session_row[2],
                    "is_active": session_row[3],
                    "created_at": str(session_row[4]),
                    "updated_at": str(session_row[5]),
                    "messages": messages,
                }
        except Exception as e:
            logger.error("Failed to get session", error=str(e))
            return None

    async def list_sessions(
        self, user_id: str = "anonymous", limit: int = 20, offset: int = 0
    ) -> list[dict[str, Any]]:
        """List recent sessions for a user with pagination."""
        try:
            async with get_db_session() as db:
                result = await db.execute(
                    text(
                        "SELECT id, title, created_at, updated_at "
                        "FROM sessions WHERE user_id = :uid AND is_active = TRUE "
                        "ORDER BY updated_at DESC LIMIT :lim OFFSET :off"
                    ),
                    {"uid": user_id, "lim": limit, "off": offset},
                )
                return [
                    {
                        "id": row[0],
                        "title": row[1],
                        "created_at": str(row[2]),
                        "updated_at": str(row[3]),
                    }
                    for row in result.fetchall()
                ]
        except Exception as e:
            logger.error("Failed to list sessions", error=str(e))
            return []

    async def update_message(self, message_id: str, content: str) -> bool:
        """Update a message's content."""
        try:
            async with get_db_session() as db:
                await db.execute(
                    text("UPDATE messages SET content = :content WHERE id = :mid"),
                    {"content": content, "mid": message_id},
                )
            return True
        except Exception as e:
            logger.error("Failed to update message", error=str(e))
            return False

    async def delete_messages_after(self, session_id: str, message_id: str) -> int:
        """Delete all messages after a given message in a session. Returns count deleted."""
        try:
            async with get_db_session() as db:
                # Get the timestamp of the target message
                result = await db.execute(
                    text("SELECT created_at FROM messages WHERE id = :mid"),
                    {"mid": message_id},
                )
                row = result.fetchone()
                if not row:
                    return 0

                result = await db.execute(
                    text("DELETE FROM messages WHERE session_id = :sid AND created_at > :ts"),
                    {"sid": session_id, "ts": row[0]},
                )
                return result.rowcount
        except Exception as e:
            logger.error("Failed to delete messages after", error=str(e))
            return 0

    async def get_message(self, message_id: str) -> dict[str, Any] | None:
        """Get a single message by ID."""
        try:
            async with get_db_session() as db:
                result = await db.execute(
                    text("SELECT id, session_id, role, content, metadata, created_at "
                         "FROM messages WHERE id = :mid"),
                    {"mid": message_id},
                )
                row = result.fetchone()
                if not row:
                    return None
                return {
                    "id": row[0],
                    "session_id": row[1],
                    "role": row[2],
                    "content": row[3],
                    "metadata": row[4] if isinstance(row[4], dict) else {},
                    "created_at": str(row[5]),
                }
        except Exception as e:
            logger.error("Failed to get message", error=str(e))
            return None

    async def delete_session(self, session_id: str) -> bool:
        """Soft-delete a session."""
        try:
            async with get_db_session() as db:
                await db.execute(
                    text("UPDATE sessions SET is_active = FALSE WHERE id = :sid"),
                    {"sid": session_id},
                )
            return True
        except Exception as e:
            logger.error("Failed to delete session", error=str(e))
            return False

    async def save_evaluation(
        self,
        session_id: str,
        query: str,
        answer: str,
        contexts: list[str],
        metrics: dict[str, Any],
        latency_ms: int = 0,
    ) -> None:
        """Save RAGAS evaluation results."""
        try:
            async with get_db_session() as db:
                import uuid
                eval_id = str(uuid.uuid4())
                await db.execute(
                    text(
                        "INSERT INTO evaluations (id, session_id, query, answer, contexts, "
                        "metrics, faithfulness, answer_relevance, context_precision, latency_ms) "
                        "VALUES (:id, :sid, :query, :answer, :contexts, :metrics, "
                        ":faith, :rel, :prec, :lat)"
                    ),
                    {
                        "id": eval_id,
                        "sid": session_id,
                        "query": query,
                        "answer": answer,
                        "contexts": json.dumps(contexts, ensure_ascii=False),
                        "metrics": json.dumps(metrics, ensure_ascii=False),
                        "faith": metrics.get("faithfulness"),
                        "rel": metrics.get("answer_relevance"),
                        "prec": metrics.get("context_precision"),
                        "lat": latency_ms,
                    },
                )
        except Exception as e:
            logger.error("Failed to save evaluation", error=str(e))

    async def search_messages(
        self,
        query: str,
        user_id: str = "anonymous",
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """
        Full-text search across conversation history.

        Uses MySQL FULLTEXT with ngram parser for Chinese support.
        Returns matching messages with session context.
        """
        try:
            async with get_db_session() as db:
                result = await db.execute(
                    text(
                        "SELECT m.session_id, m.role, m.content, m.created_at, "
                        "s.title AS session_title "
                        "FROM messages m "
                        "JOIN sessions s ON m.session_id = s.id "
                        "WHERE s.user_id = :uid AND s.is_active = TRUE "
                        "AND MATCH(m.content) AGAINST(:query IN NATURAL LANGUAGE MODE) "
                        "ORDER BY m.created_at DESC LIMIT :lim"
                    ),
                    {"uid": user_id, "query": query, "lim": limit},
                )
                return [
                    {
                        "session_id": row[0],
                        "role": row[1],
                        "content": row[2][:300] + "..." if len(row[2]) > 300 else row[2],
                        "created_at": str(row[3]),
                        "session_title": row[4],
                    }
                    for row in result.fetchall()
                ]
        except Exception as e:
            logger.error("Failed to search messages", error=str(e))
            return []


# Global instance
session_repo = SessionRepository()
