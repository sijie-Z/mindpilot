"""
Pluggable ContextEngine with lifecycle hooks (inspired by Hermes Agent).

Manages conversation context window with configurable compression strategies.
Protects head (system + first messages) and tail (recent messages) during compression.

Usage:
    engine = ContextEngine(strategy="summarize", llm=llm)
    engine.on_session_start(session_id)
    messages = engine.build_messages(query, context)
    # ... after response ...
    engine.update_from_response(response)
    if engine.should_compress():
        compressed = await engine.compress()
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.core.logger import get_logger

logger = get_logger(__name__)

# Default compression parameters
DEFAULT_MAX_TOKENS = 8000
DEFAULT_HEAD_MESSAGES = 2  # Protect system + first user message
DEFAULT_TAIL_MESSAGES = 4  # Protect recent conversation
DEFAULT_COMPRESS_RATIO = 0.20  # 20% of compressed content
DEFAULT_MAX_SUMMARY_TOKENS = 12000


@dataclass
class ContextMessage:
    """A message in the conversation context."""
    role: str
    content: str
    timestamp: float = field(default_factory=time.time)
    token_estimate: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.token_estimate == 0:
            # Rough estimate: 1 token per 2 chars for Chinese, 4 for English
            self.token_estimate = len(self.content) // 2


class CompressionStrategy(ABC):
    """Abstract base for context compression strategies."""

    @abstractmethod
    async def compress(self, messages: list[ContextMessage]) -> str:
        """Compress a list of messages into a summary string."""
        ...


class TruncationStrategy(CompressionStrategy):
    """Simple truncation: keep head + tail, drop middle."""

    def __init__(self, head: int = DEFAULT_HEAD_MESSAGES, tail: int = DEFAULT_TAIL_MESSAGES):
        self.head = head
        self.tail = tail

    async def compress(self, messages: list[ContextMessage]) -> str:
        if len(messages) <= self.head + self.tail:
            return ""

        dropped = messages[self.head:-self.tail]
        total_dropped = sum(m.token_estimate for m in dropped)
        return f"[已压缩 {len(dropped)} 条历史消息，约 {total_dropped} tokens]"


class SummarizeStrategy(CompressionStrategy):
    """LLM-based summarization of middle messages."""

    def __init__(self, llm: Any = None, head: int = DEFAULT_HEAD_MESSAGES, tail: int = DEFAULT_TAIL_MESSAGES):
        self.llm = llm
        self.head = head
        self.tail = tail

    async def compress(self, messages: list[ContextMessage]) -> str:
        if len(messages) <= self.head + self.tail:
            return ""

        dropped = messages[self.head:-self.tail]
        conversation = "\n".join(
            f"{m.role}: {m.content[:200]}" for m in dropped
        )

        if self.llm is None:
            return await TruncationStrategy(self.head, self.tail).compress(messages)

        try:
            prompt = (
                "请用中文简洁总结以下对话的要点，保留关键信息和决策，"
                "丢弃闲聊和重复内容。控制在200字以内。\n\n"
                f"对话内容：\n{conversation[:4000]}"
            )
            summary = await self.llm.chat(messages=[{"role": "user", "content": prompt}])
            return f"[对话摘要] {summary}"
        except Exception as e:
            logger.warning("Summarization failed, falling back to truncation", error=str(e))
            return await TruncationStrategy(self.head, self.tail).compress(messages)


class ContextEngine:
    """
    Manages conversation context with pluggable compression.

    Lifecycle:
    1. on_session_start(session_id) - initialize
    2. add_message(role, content) - add messages
    3. build_messages(query, extra_context) - build prompt
    4. update_from_response(response) - post-turn update
    5. should_compress() - check if compression needed
    6. compress() - compress middle messages
    7. on_session_end() - cleanup
    """

    def __init__(
        self,
        strategy: CompressionStrategy | str = "summarize",
        llm: Any = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ):
        self.max_tokens = max_tokens
        self.messages: list[ContextMessage] = []
        self.session_id: str | None = None
        self._compressed_summary: str = ""
        self._turn_count = 0

        if isinstance(strategy, str):
            if strategy == "summarize":
                self._strategy = SummarizeStrategy(llm=llm)
            else:
                self._strategy = TruncationStrategy()
        else:
            self._strategy = strategy

    def on_session_start(self, session_id: str) -> None:
        """Initialize context for a new session."""
        self.session_id = session_id
        self.messages = []
        self._compressed_summary = ""
        self._turn_count = 0
        logger.debug("Context engine initialized", session_id=session_id)

    def add_message(self, role: str, content: str, **metadata: Any) -> None:
        """Add a message to the context."""
        self.messages.append(ContextMessage(
            role=role,
            content=content,
            metadata=metadata,
        ))
        self._turn_count += 1

    def build_messages(
        self,
        query: str,
        system_prompt: str = "",
        extra_context: str = "",
    ) -> list[dict[str, str]]:
        """Build message list for LLM, including compressed summary if present."""
        result: list[dict[str, str]] = []

        if system_prompt:
            result.append({"role": "system", "content": system_prompt})

        if self._compressed_summary:
            result.append({"role": "system", "content": self._compressed_summary})

        if extra_context:
            result.append({"role": "system", "content": extra_context})

        for msg in self.messages:
            result.append({"role": msg.role, "content": msg.content})

        result.append({"role": "user", "content": query})
        return result

    def update_from_response(self, response: str) -> None:
        """Post-turn update: add assistant response to context."""
        self.add_message("assistant", response)

    def should_compress(self) -> bool:
        """Check if context exceeds token budget."""
        total_tokens = sum(m.token_estimate for m in self.messages)
        return total_tokens > self.max_tokens

    async def compress(self) -> str:
        """Compress middle messages using configured strategy."""
        if len(self.messages) <= DEFAULT_HEAD_MESSAGES + DEFAULT_TAIL_MESSAGES:
            return ""

        summary = await self._strategy.compress(self.messages)
        if summary:
            self._compressed_summary = (
                f"{self._compressed_summary}\n{summary}".strip()
                if self._compressed_summary
                else summary
            )
            # Keep head + tail only
            head = self.messages[:DEFAULT_HEAD_MESSAGES]
            tail = self.messages[-DEFAULT_TAIL_MESSAGES:]
            dropped_count = len(self.messages) - len(head) - len(tail)
            self.messages = head + tail
            logger.info(
                "Context compressed",
                dropped_messages=dropped_count,
                remaining=len(self.messages),
                summary_len=len(summary),
            )
        return summary

    def get_context_stats(self) -> dict[str, Any]:
        """Get current context statistics."""
        total_tokens = sum(m.token_estimate for m in self.messages)
        return {
            "session_id": self.session_id,
            "message_count": len(self.messages),
            "estimated_tokens": total_tokens,
            "max_tokens": self.max_tokens,
            "turn_count": self._turn_count,
            "has_compressed_summary": bool(self._compressed_summary),
            "summary_length": len(self._compressed_summary),
        }

    def on_session_end(self) -> None:
        """Cleanup on session end."""
        logger.debug(
            "Context engine session ended",
            session_id=self.session_id,
            total_turns=self._turn_count,
            final_message_count=len(self.messages),
        )
