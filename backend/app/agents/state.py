"""
Agent state definition for LangGraph multi-agent orchestration.
"""
from datetime import datetime
from typing import Any, TypedDict

from pydantic import BaseModel


class Query(BaseModel):
    """Query input model."""
    query: str
    session_id: str | None = None
    user_id: str | None = None
    knowledge_id: str | None = None
    stream: bool = True


class Source(BaseModel):
    """Source citation."""
    filename: str
    page: int | None = None
    chunk_id: str
    content: str
    score: float = 0.0


class AgentState(TypedDict):
    """Shared state for multi-agent workflow with LangGraph."""

    # ── Input ──
    query: str
    session_id: str
    user_id: str
    knowledge_id: str | None
    model: str | None  # LLM model to use for this request

    # ── Intent ──
    intent: str
    intent_confidence: float

    # ── Retrieval ──
    retrieved_docs: list[dict[str, Any]]
    expanded_queries: list[str]
    reranked_docs: list[dict[str, Any]]
    retrieval_attempts: int  # track retry count for quality loop

    # ── Skill results ──
    skill_results: dict[str, Any]

    # ── Generation ──
    answer: str
    sources: list[dict[str, Any]]
    streaming: bool

    # ── Evaluation ──
    evaluation: dict[str, float]
    status: str

    # ── Messages (for multi-turn conversation memory) ──
    messages: list[dict[str, Any]]

    # ── Meta ──
    created_at: datetime
    latency_ms: int
    iterations: int
    max_iterations: int

    # ── Quality loop control ──
    quality_passed: bool
    quality_feedback: str


class SSEEvent(BaseModel):
    """SSE event model."""
    type: str
    content: str | None = None
    data: dict[str, Any] | None = None
