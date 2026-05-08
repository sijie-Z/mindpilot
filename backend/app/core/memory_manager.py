"""
MemoryManager with prefetch/sync lifecycle (inspired by Hermes Agent).

Single integration point that orchestrates memory providers:
- prefetch_all(): pre-turn memory loading
- sync_all(): post-turn memory persistence
- build_system_prompt(): inject memories into context

Usage:
    manager = MemoryManager(session_repo, llm)
    context = await manager.prefetch_all(session_id, user_id)
    # ... agent runs ...
    await manager.sync_all(session_id, user_id, response)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class MemoryContext:
    """Aggregated memory context for a session."""
    session_history: list[dict[str, Any]] = field(default_factory=list)
    relevant_memories: list[str] = field(default_factory=list)
    user_preferences: dict[str, Any] = field(default_factory=dict)
    compressed_summary: str = ""
    total_tokens: int = 0

    def to_prompt_context(self) -> str:
        """Convert memory context to prompt injection string."""
        parts = []
        if self.compressed_summary:
            parts.append(f"[历史摘要]\n{self.compressed_summary}")
        if self.relevant_memories:
            parts.append("[相关记忆]\n" + "\n".join(f"- {m}" for m in self.relevant_memories))
        if self.user_preferences:
            prefs = ", ".join(f"{k}: {v}" for k, v in self.user_preferences.items())
            parts.append(f"[用户偏好] {prefs}")
        return "\n\n".join(parts)


class MemoryManager:
    """
    Orchestrates memory providers with prefetch/sync lifecycle.

    Lifecycle:
    1. prefetch_all() - Load memories before agent turn
    2. Agent runs with memory context
    3. sync_all() - Persist new memories after agent turn
    """

    def __init__(self, session_repo: Any = None, llm: Any = None):
        self.session_repo = session_repo
        self.llm = llm
        self._cache: dict[str, MemoryContext] = {}

    async def prefetch_all(
        self,
        session_id: str,
        user_id: str = "anonymous",
        current_query: str = "",
    ) -> MemoryContext:
        """
        Pre-turn: load all relevant memories.

        Returns MemoryContext with session history, relevant memories,
        and compressed summary if available.
        """
        context = MemoryContext()

        # 1. Load session history
        if self.session_repo:
            try:
                session = await self.session_repo.get_session(session_id)
                if session:
                    context.session_history = session.get("messages", [])
            except Exception as e:
                logger.warning("Failed to load session history", error=str(e))

        # 2. Search for relevant cross-session memories
        if self.session_repo and current_query:
            try:
                results = await self.session_repo.search_messages(
                    query=current_query,
                    user_id=user_id,
                    limit=5,
                )
                context.relevant_memories = [
                    f"[{r.get('created_at', '')}] {r.get('content', '')[:150]}"
                    for r in results
                    if r.get("session_id") != session_id  # Exclude current session
                ]
            except Exception as e:
                logger.warning("Failed to search memories", error=str(e))

        # 3. Compress old session history if needed
        if len(context.session_history) > 20 and self.llm:
            context.compressed_summary = await self._compress_history(
                context.session_history[:-6]
            )
            context.session_history = context.session_history[-6:]

        # Cache for post-turn sync
        self._cache[session_id] = context
        return context

    async def sync_all(
        self,
        session_id: str,
        user_id: str = "anonymous",
        response: str = "",
    ) -> None:
        """
        Post-turn: persist new memories and update cache.
        """
        context = self._cache.get(session_id)
        if not context:
            return

        # Update cached context with new response
        if response:
            context.session_history.append({
                "role": "assistant",
                "content": response,
            })

        # Memory sync is handled by session_repo.add_message() in the chat flow
        logger.debug(
            "Memory sync completed",
            session_id=session_id,
            history_len=len(context.session_history),
            memories_count=len(context.relevant_memories),
        )

    async def _compress_history(self, messages: list[dict[str, Any]]) -> str:
        """Compress old messages into a summary."""
        if not self.llm:
            return ""

        conversation = "\n".join(
            f"{m.get('role', 'unknown')}: {m.get('content', '')[:200]}"
            for m in messages
        )

        try:
            prompt = (
                "请用中文简洁总结以下对话的要点，保留关键信息和决策，"
                "控制在200字以内。\n\n"
                f"对话内容：\n{conversation[:4000]}"
            )
            return await self.llm.chat(messages=[{"role": "user", "content": prompt}])
        except Exception as e:
            logger.warning("History compression failed", error=str(e))
            return f"[已压缩 {len(messages)} 条历史消息]"

    def clear_cache(self, session_id: str | None = None) -> None:
        """Clear memory cache for a session or all sessions."""
        if session_id:
            self._cache.pop(session_id, None)
        else:
            self._cache.clear()
