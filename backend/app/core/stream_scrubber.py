"""
StreamingContextScrubber for SSE safety (inspired by Hermes Agent).

State machine that prevents internal context from leaking into
SSE streamed responses. Scrubs:
- System prompts and agent instructions
- Retrieved document metadata (IDs, embeddings, internal scores)
- Agent state keys (intent, quality scores, internal routing)
- Debug/log information

Usage:
    scrubber = StreamScrubber()
    async for chunk in stream:
        safe_chunk = scrubber.scrub(chunk)
        yield safe_chunk
"""
from __future__ import annotations

import json
import re
from enum import Enum, auto
from typing import Any

from app.core.logger import get_logger

logger = get_logger(__name__)

# Patterns that should never appear in user-facing output
_SENSITIVE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\[INST\]|\[/INST\]|<\|im_start\|>|<\|im_end\|>"),  # Prompt templates
    re.compile(r"system:\s*You are", re.IGNORECASE),  # System prompts
    re.compile(r"embedding_id|vector_id|chunk_id", re.IGNORECASE),  # Internal IDs
    re.compile(r"rerank_score|relevance_score|faithfulness", re.IGNORECASE),  # Internal scores
    re.compile(r"session_id.*[0-9a-f]{8}-[0-9a-f]{4}", re.IGNORECASE),  # UUIDs in context
]

# JSON keys that should be stripped from streamed JSON fragments
_SCRUBBED_JSON_KEYS: set[str] = {
    "embedding_id", "vector_id", "chunk_id", "doc_id",
    "rerank_score", "relevance_score", "faithfulness_score",
    "internal_state", "agent_metadata", "debug_info",
    "token_count", "model_name", "prompt_tokens",
}


class ScrubState(Enum):
    """State machine for stream scrubbing."""
    NORMAL = auto()
    IN_JSON = auto()
    IN_CODE_BLOCK = auto()
    IN_SYSTEM_LEAK = auto()


class StreamScrubber:
    """
    State machine that scrubs internal context from streamed responses.

    Handles edge cases:
    - Partial JSON fragments across chunks
    - Code blocks (should not scrub code)
    - Multi-chunk system prompt leaks
    """

    def __init__(self) -> None:
        self._state = ScrubState.NORMAL
        self._buffer = ""
        self._code_block_depth = 0
        self._scrubbed_count = 0

    def scrub(self, chunk: str) -> str:
        """
        Scrub a single chunk of streamed output.

        Returns the safe portion of the chunk.
        """
        if not chunk:
            return ""

        self._buffer += chunk
        result = ""

        while self._buffer:
            if self._state == ScrubState.NORMAL:
                result += self._process_normal()
            elif self._state == ScrubState.IN_CODE_BLOCK:
                result += self._process_code_block()
            elif self._state == ScrubState.IN_JSON:
                result += self._process_json()
            elif self._state == ScrubState.IN_SYSTEM_LEAK:
                result += self._process_system_leak()

        return result

    def _process_normal(self) -> str:
        """Process buffer in normal text state."""
        if not self._buffer:
            return ""

        # Check for code block start/end
        code_start = self._buffer.find("```")
        if code_start != -1:
            self._code_block_depth += 1
            self._state = ScrubState.IN_CODE_BLOCK
            before = self._buffer[:code_start]
            self._buffer = self._buffer[code_start:]
            return self._scrub_text(before)

        # Check for system prompt leak patterns
        for pattern in _SENSITIVE_PATTERNS:
            match = pattern.search(self._buffer)
            if match:
                self._state = ScrubState.IN_SYSTEM_LEAK
                before = self._buffer[:match.start()]
                self._buffer = self._buffer[match.start():]
                return self._scrub_text(before)

        # Check for JSON object start
        json_start = self._buffer.find("{")
        if json_start != -1 and json_start < 50:  # Near start of buffer
            self._state = ScrubState.IN_JSON
            before = self._buffer[:json_start]
            self._buffer = self._buffer[json_start:]
            return self._scrub_text(before)

        # All clear, return buffer
        result = self._scrub_text(self._buffer)
        self._buffer = ""
        return result

    def _process_code_block(self) -> str:
        """Process buffer inside a code block (don't scrub content)."""
        end = self._buffer.find("```")
        if end != -1:
            end += 3  # Include closing backticks
            self._code_block_depth = max(0, self._code_block_depth - 1)
            self._state = ScrubState.NORMAL
            result = self._buffer[:end]
            self._buffer = self._buffer[end:]
            return result

        # Still in code block, return all
        result = self._buffer
        self._buffer = ""
        return result

    def _process_json(self) -> str:
        """Process buffer looking for complete JSON to scrub."""
        # Try to find complete JSON object
        depth = 0
        for i, ch in enumerate(self._buffer):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    # Complete JSON found
                    json_str = self._buffer[:i + 1]
                    self._buffer = self._buffer[i + 1:]
                    self._state = ScrubState.NORMAL
                    return self._scrub_json(json_str)

        # Incomplete JSON — flush as text to avoid blocking the stream
        result = self._scrub_text(self._buffer)
        self._buffer = ""
        self._state = ScrubState.NORMAL
        return result

    def _process_system_leak(self) -> str:
        """Process buffer to skip system prompt leak."""
        # Skip until we find a newline or end of pattern
        nl = self._buffer.find("\n")
        if nl != -1:
            self._buffer = self._buffer[nl + 1:]
            self._state = ScrubState.NORMAL
            self._scrubbed_count += 1
            return ""

        # Whole buffer is a leak
        self._scrubbed_count += 1
        self._buffer = ""
        self._state = ScrubState.NORMAL
        return ""

    def _scrub_text(self, text: str) -> str:
        """Scrub sensitive patterns from text."""
        if not text:
            return ""
        for pattern in _SENSITIVE_PATTERNS:
            text = pattern.sub("[已过滤]", text)
        return text

    def _scrub_json(self, json_str: str) -> str:
        """Scrub sensitive keys from JSON object."""
        try:
            data = json.loads(json_str)
            if isinstance(data, dict):
                scrubbed = {k: v for k, v in data.items() if k not in _SCRUBBED_JSON_KEYS}
                return json.dumps(scrubbed, ensure_ascii=False)
        except json.JSONDecodeError:
            pass
        return json_str

    @property
    def stats(self) -> dict[str, Any]:
        """Get scrubber statistics."""
        return {
            "state": self._state.name,
            "scrubbed_count": self._scrubbed_count,
            "buffer_size": len(self._buffer),
        }
