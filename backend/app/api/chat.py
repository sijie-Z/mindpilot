"""
Chat API with SSE streaming and non-streaming endpoints.
Uses the LangGraph agent graph with real conditional routing.
"""
import json
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import text

from app.agents.answer_agent import answer_node, generate_answer_stream
from app.agents.eval_agent import eval_node
from app.agents.graph import run_agent
from app.agents.intent_agent import intent_node
from app.agents.retrieval_agent import expand_query, retrieval_node
from app.agents.state import AgentState
from app.auth import TokenData, get_current_user, get_optional_user
from app.core.container import container as ctx
from app.core.llm_client import AsyncLLMClient
from app.core.logger import get_logger
from app.storage.database import get_db_session

logger = get_logger(__name__)
router = APIRouter()

# Constants
IMAGE_CONTEXT_MAX_LENGTH = 500
SESSION_TITLE_MAX_LENGTH = 30


async def _generate_session_title(query: str, llm: AsyncLLMClient) -> str | None:
    """Generate a concise session title from the first user message using LLM."""
    try:
        title = await llm.chat(
            messages=[{
                "role": "user",
                "content": (
                    f"为以下对话生成一个简短标题（不超过20个字），直接输出标题，不要引号或标点：\n{query[:200]}"
                ),
            }],
            max_tokens=50,
            temperature=0.3,
        )
        title = title.strip().strip('"').strip("'").strip("《》").strip()
        return title[:30] if title else None
    except Exception as e:
        logger.warning("Title generation failed", error=str(e))
        return None


async def _update_session_title(session_id: str, query: str, llm: AsyncLLMClient):
    """Background task: generate and update session title."""
    title = await _generate_session_title(query, llm)
    if title:
        try:
            async with get_db_session() as db:
                await db.execute(
                    text("UPDATE sessions SET title = :title WHERE id = :sid"),
                    {"title": title, "sid": session_id},
                )
        except Exception as e:
            logger.warning("Failed to update session title", error=str(e))


class ChatRequest(BaseModel):
    """Chat request model with optional image support."""
    query: str
    session_id: str | None = None
    user_id: str | None = None
    knowledge_id: str | None = None
    model: str | None = None  # LLM model to use (e.g., "glm-4-flash", "glm-4-plus")
    image_url: str | None = None  # Base64 or URL for multimodal queries
    image_base64: str | None = None  # Direct base64 image data


class ChatResponse(BaseModel):
    """Chat response model."""
    answer: str
    sources: list
    evaluation: dict
    session_id: str


def build_initial_state(request: ChatRequest, session_id: str, streaming: bool, history: list | None = None) -> AgentState:
    """Build initial AgentState from request with optional conversation history."""
    return {
        "query": request.query,
        "session_id": session_id,
        "user_id": request.user_id or "anonymous",
        "knowledge_id": request.knowledge_id,
        "model": request.model,
        "streaming": streaming,
        "iterations": 0,
        "retrieval_attempts": 0,
        "quality_passed": True,
        "quality_feedback": "",
        "intent": "general",
        "intent_confidence": 0.0,
        "retrieved_docs": [],
        "expanded_queries": [],
        "reranked_docs": [],
        "skill_results": {},
        "answer": "",
        "sources": [],
        "evaluation": {},
        "status": "thinking",
        "messages": history or [],
        "created_at": None,
        "latency_ms": 0,
        "max_iterations": 5,
    }


async def _load_session_history(session_id: str, max_turns: int = 10) -> list[dict]:
    """Load recent conversation history for context."""
    try:
        from sqlalchemy import text
        async with get_db_session() as db:
            result = await db.execute(
                text("SELECT role, content FROM messages "
                     "WHERE session_id = :sid AND role IN ('user', 'assistant') "
                     "ORDER BY created_at DESC LIMIT :lim"),
                {"sid": session_id, "lim": max_turns * 2},
            )
            rows = result.fetchall()
            # Reverse to chronological order
            return [{"role": r[0], "content": r[1]} for r in reversed(rows)]
    except Exception:
        return []


async def stream_chat(request: ChatRequest) -> str:
    """SSE streaming chat with real-time status updates."""
    llm = AsyncLLMClient()
    if request.model:
        llm._model = request.model
    session_id = request.session_id or str(uuid.uuid4())

    # Initialize stream scrubber to prevent context leakage
    from app.core.stream_scrubber import StreamScrubber
    scrubber = StreamScrubber()

    # Connected
    yield f"data: {json.dumps({'type': 'connected', 'session_id': session_id})}\n\n"

    # Load conversation history for context
    history = await _load_session_history(session_id) if request.session_id else []
    state = build_initial_state(request, session_id, streaming=True, history=history)

    try:
        # ── Persist session (use query snippet as initial title) ──
        initial_title = request.query[:SESSION_TITLE_MAX_LENGTH]
        await ctx.session_repo.create_session(session_id, request.user_id or "anonymous", initial_title)
        await ctx.session_repo.add_message(session_id, "user", request.query)

        # ── Generate better title in background ──
        import asyncio
        asyncio.create_task(_update_session_title(session_id, request.query, llm))

        # ── Step 0: Image processing (if image provided) ──
        image_context = ""
        if request.image_base64 or request.image_url:
            yield f"data: {json.dumps({'type': 'status', 'content': '正在分析图片...'})}\n\n"
            try:
                from app.multimodal.vision import VisionProcessor
                vision = VisionProcessor(llm)
                if request.image_base64:
                    image_context = await vision.describe_image_base64(request.image_base64)
                elif request.image_url:
                    image_context = f"[图片URL: {request.image_url}]"
                state["query"] = f"{request.query}\n\n[图片描述: {image_context[:IMAGE_CONTEXT_MAX_LENGTH]}]"
                yield f"data: {json.dumps({'type': 'status', 'content': '图片分析完成'})}\n\n"
            except Exception as e:
                logger.warning("Image analysis failed, continuing without image context", error=str(e))

        # ── Step 1: Intent ──
        yield f"data: {json.dumps({'type': 'status', 'content': '正在理解您的问题...'})}\n\n"
        state = await intent_node(state, llm=llm)
        yield f"data: {json.dumps({'type': 'intent', 'content': state['intent']})}\n\n"

        # ── Step 2: Retrieval (only for doc_qa) ──
        if state["intent"] == "doc_qa":
            yield f"data: {json.dumps({'type': 'status', 'content': '正在扩展搜索策略...'})}\n\n"

            expanded = await expand_query(request.query, llm)
            state["expanded_queries"] = expanded
            yield f"data: {json.dumps({'type': 'expansion', 'content': expanded})}\n\n"

            yield f"data: {json.dumps({'type': 'status', 'content': '正在从知识库检索文档...'})}\n\n"

            state = await retrieval_node(state, llm=llm)
            yield f"data: {json.dumps({'type': 'retrieval', 'count': len(state.get('retrieved_docs', []))})}\n\n"

            yield f"data: {json.dumps({'type': 'status', 'content': '正在重排序结果...'})}\n\n"
            yield f"data: {json.dumps({'type': 'rerank', 'top_k': len(state.get('reranked_docs', []))})}\n\n"

        # ── Step 3: Generate answer ──
        yield f"data: {json.dumps({'type': 'status', 'content': '正在生成回答...'})}\n\n"

        state = await answer_node(state, llm=llm)

        if state["intent"] == "doc_qa" and state.get("reranked_docs"):
            # Stream RAG answer chunk by chunk (with scrubbing)
            async for chunk in generate_answer_stream(request.query, state["reranked_docs"], llm):
                safe_chunk = scrubber.scrub(chunk)
                if safe_chunk:
                    yield f"data: {json.dumps({'type': 'answer', 'content': safe_chunk, 'chunk': True})}\n\n"
        else:
            safe_answer = scrubber.scrub(state['answer'])
            yield f"data: {json.dumps({'type': 'answer', 'content': safe_answer, 'chunk': False})}\n\n"

        # ── Step 4: Sources ──
        for i, source in enumerate(state.get("sources", [])):
            yield f"data: {json.dumps({'type': 'source', 'source': source, 'index': i})}\n\n"

        # ── Step 5: Evaluation ──
        if state["intent"] == "doc_qa" and state.get("reranked_docs"):
            state = await eval_node(state, llm=llm)
            yield f"data: {json.dumps({'type': 'evaluation', 'data': state['evaluation']})}\n\n"

            # Save evaluation to database for analytics dashboard
            evaluation = state.get("evaluation", {})
            if evaluation and not evaluation.get("skipped"):
                await ctx.session_repo.save_evaluation(
                    session_id=session_id,
                    query=request.query,
                    answer=state.get("answer", ""),
                    contexts=[s.get("content", "")[:200] for s in state.get("sources", [])],
                    metrics=evaluation,
                    latency_ms=state.get("latency_ms", 0),
                )

        # ── Persist assistant message ──
        answer_text = state.get("answer", "")
        sources = state.get("sources", [])
        evaluation = state.get("evaluation", {})
        await ctx.session_repo.add_message(
            session_id, "assistant", answer_text,
            metadata={"sources": sources, "evaluation": evaluation},
        )

        yield f"data: {json.dumps({'type': 'done', 'latency_ms': state.get('latency_ms', 0)})}\n\n"

    except Exception as e:
        logger.error("Stream chat failed", error=str(e))
        yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    current_user: TokenData | None = Depends(get_optional_user),
):
    """Stream chat response with SSE events and real-time status updates."""
    logger.info("SSE stream started", query=request.query[:80])

    return StreamingResponse(
        stream_chat(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: TokenData | None = Depends(get_optional_user),
):
    """Non-streaming chat using the full agent graph with conditional routing."""
    logger.info("Chat request", query=request.query[:80])

    session_id = request.session_id or str(uuid.uuid4())

    # Load conversation history for context
    history = await _load_session_history(session_id) if request.session_id else []
    state = build_initial_state(request, session_id, streaming=False, history=history)

    try:
        # ── Persist session ──
        initial_title = request.query[:SESSION_TITLE_MAX_LENGTH]
        await ctx.session_repo.create_session(session_id, request.user_id or "anonymous", initial_title)
        await ctx.session_repo.add_message(session_id, "user", request.query)

        # ── Generate better title in background ──
        import asyncio
        llm = AsyncLLMClient()
        asyncio.create_task(_update_session_title(session_id, request.query, llm))

        # ── Run agent graph (model is passed via state) ──
        result = await run_agent(state, thread_id=session_id)

        answer = result.get("answer", "")
        sources = result.get("sources", [])
        evaluation = result.get("evaluation", {})

        # ── Save assistant message ──
        await ctx.session_repo.add_message(
            session_id, "assistant", answer,
            metadata={"sources": sources, "evaluation": evaluation},
        )

        # ── Save evaluation if present ──
        if evaluation and not evaluation.get("skipped"):
            await ctx.session_repo.save_evaluation(
                session_id=session_id,
                query=request.query,
                answer=answer,
                contexts=[s.get("content", "")[:200] for s in sources],
                metrics=evaluation,
                latency_ms=result.get("latency_ms", 0),
            )

        return ChatResponse(answer=answer, sources=sources, evaluation=evaluation, session_id=session_id)
    except Exception as e:
        logger.error("Chat failed", error=str(e))
        raise HTTPException(status_code=500, detail="An error occurred while processing your request")


# ── Session management endpoints ──

@router.get("/sessions")
async def list_sessions(
    user_id: str = "anonymous",
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: TokenData | None = Depends(get_optional_user),
):
    """List recent chat sessions with pagination."""
    sessions = await ctx.session_repo.list_sessions(user_id, limit=limit, offset=offset)
    return {"sessions": sessions, "limit": limit, "offset": offset}


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    current_user: TokenData | None = Depends(get_optional_user),
):
    """Get a session with all messages."""
    session = await ctx.session_repo.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    current_user: TokenData = Depends(get_current_user),
):
    """Delete (archive) a session."""
    success = await ctx.session_repo.delete_session(session_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete session")
    return {"status": "deleted", "session_id": session_id}


class EditMessageRequest(BaseModel):
    content: str


@router.put("/messages/{message_id}")
async def edit_message(
    message_id: str,
    req: EditMessageRequest,
    current_user: TokenData | None = Depends(get_optional_user),
):
    """Edit a user message and delete all subsequent messages (triggers re-generation)."""
    msg = await ctx.session_repo.get_message(message_id)
    if not msg:
        raise HTTPException(404, "Message not found")
    if msg["role"] != "user":
        raise HTTPException(400, "Can only edit user messages")

    # Update the message content
    success = await ctx.session_repo.update_message(message_id, req.content)
    if not success:
        raise HTTPException(500, "Failed to update message")

    # Delete all messages after this one (assistant responses, etc.)
    deleted = await ctx.session_repo.delete_messages_after(msg["session_id"], message_id)

    return {
        "status": "updated",
        "message_id": message_id,
        "deleted_after": deleted,
        "session_id": msg["session_id"],
    }


@router.post("/sessions/{session_id}/share")
async def share_session(
    session_id: str,
    current_user: TokenData | None = Depends(get_optional_user),
):
    """Create a public share link for a session."""
    import uuid
    share_id = str(uuid.uuid4())[:12]

    async with get_db_session() as db:
        result = await db.execute(
            text("SELECT id FROM sessions WHERE id = :sid"),
            {"sid": session_id}
        )
        if not result.fetchone():
            raise HTTPException(404, "Session not found")

        await db.execute(
            text("UPDATE sessions SET share_id = :share_id WHERE id = :sid"),
            {"share_id": share_id, "sid": session_id}
        )

    return {"share_id": share_id, "url": f"/share/{share_id}"}


@router.delete("/sessions/{session_id}/share")
async def unshare_session(
    session_id: str,
    current_user: TokenData | None = Depends(get_optional_user),
):
    """Remove the share link for a session."""
    async with get_db_session() as db:
        await db.execute(
            text("UPDATE sessions SET share_id = NULL WHERE id = :sid"),
            {"sid": session_id}
        )
    return {"status": "unshared"}


@router.get("/share/{share_id}")
async def get_shared_session(share_id: str):
    """Get a shared session by its share ID (no auth required)."""
    async with get_db_session() as db:
        result = await db.execute(
            text("SELECT id, title, created_at FROM sessions WHERE share_id = :sid AND is_active = TRUE"),
            {"sid": share_id}
        )
        session = result.fetchone()
        if not session:
            raise HTTPException(404, "Shared session not found")

        msgs_result = await db.execute(
            text("SELECT role, content, metadata, created_at "
                 "FROM messages WHERE session_id = :sid ORDER BY created_at ASC"),
            {"sid": session[0]}
        )
        messages = [
            {
                "role": r[0],
                "content": r[1],
                "sources": (r[2] or {}).get("sources", []) if isinstance(r[2], dict) else [],
                "created_at": str(r[3]),
            }
            for r in msgs_result.fetchall()
        ]

    return {
        "id": session[0],
        "title": session[1],
        "created_at": str(session[2]),
        "messages": messages,
    }


@router.get("/sessions/{session_id}/export")
async def export_session(
    session_id: str,
    format: str = Query("markdown", pattern="^(markdown|json)$"),
    current_user: TokenData | None = Depends(get_optional_user),
):
    """
    Export a chat session in the specified format.

    Supported formats:
    - markdown: Human-readable Markdown document
    - json: Structured JSON with full metadata
    """
    session = await ctx.session_repo.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if format == "json":
        from fastapi.responses import JSONResponse
        return JSONResponse(
            content=session,
            headers={
                "Content-Disposition": f'attachment; filename="chat_{session_id[:8]}.json"'
            },
        )

    # Markdown format
    from fastapi.responses import PlainTextResponse

    lines = []
    lines.append(f"# {session.get('title', '对话记录')}")
    lines.append("")
    lines.append(f"**导出时间**: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"**会话 ID**: {session_id}")
    lines.append("")
    lines.append("---")
    lines.append("")

    for msg in session.get("messages", []):
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        created_at = msg.get("created_at", "")

        if role == "user":
            lines.append("## 用户")
            lines.append(f"*{created_at}*")
            lines.append("")
            lines.append(content)
            lines.append("")
        elif role == "assistant":
            lines.append("## 助手")
            lines.append(f"*{created_at}*")
            lines.append("")
            lines.append(content)
            lines.append("")

            # Add sources if available
            metadata = msg.get("metadata", {})
            sources = metadata.get("sources", [])
            if sources:
                lines.append("### 参考来源")
                lines.append("")
                for i, src in enumerate(sources, 1):
                    filename = src.get("filename", src.get("name", "未知文件"))
                    score = src.get("score", 0)
                    lines.append(f"{i}. **{filename}** (相关度: {score:.2f})")
                lines.append("")

        lines.append("---")
        lines.append("")

    md_content = "\n".join(lines)
    return PlainTextResponse(
        content=md_content,
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="chat_{session_id[:8]}.md"'
        },
    )


@router.get("/search")
async def search_conversations(
    q: str,
    user_id: str = "anonymous",
    limit: int = Query(20, ge=1, le=100),
):
    """
    Full-text search across conversation history.

    Uses MySQL FULLTEXT with ngram parser for Chinese tokenization.
    Returns matching messages with session context for cross-session recall.
    """
    if not q.strip():
        return {"results": [], "query": q}

    results = await ctx.session_repo.search_messages(
        query=q, user_id=user_id, limit=limit
    )
    return {"results": results, "query": q, "count": len(results)}
