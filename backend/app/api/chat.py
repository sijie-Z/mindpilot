"""
Chat API with SSE streaming and non-streaming endpoints.
Uses the LangGraph agent graph with real conditional routing.
"""
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.agents.answer_agent import answer_node, generate_answer_stream
from app.agents.eval_agent import eval_node
from app.agents.graph import run_agent
from app.agents.intent_agent import intent_node
from app.agents.retrieval_agent import expand_query, retrieval_node
from app.agents.state import AgentState
from app.auth import TokenData, get_optional_user
from app.core.container import container as ctx
from app.core.llm_client import AsyncLLMClient
from app.core.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


class ChatRequest(BaseModel):
    """Chat request model with optional image support."""
    query: str
    session_id: str | None = None
    user_id: str | None = None
    knowledge_id: str | None = None
    image_url: str | None = None  # Base64 or URL for multimodal queries
    image_base64: str | None = None  # Direct base64 image data


class ChatResponse(BaseModel):
    """Chat response model."""
    answer: str
    sources: list
    evaluation: dict
    session_id: str


async def stream_chat(request: ChatRequest) -> str:
    """SSE streaming chat with real-time status updates."""
    llm = AsyncLLMClient()
    session_id = request.session_id or str(uuid.uuid4())

    # Connected
    yield f"data: {json.dumps({'type': 'connected', 'session_id': session_id})}\n\n"

    state: AgentState = {
        "query": request.query,
        "session_id": session_id,
        "user_id": request.user_id or "anonymous",
        "knowledge_id": request.knowledge_id,
        "streaming": True,
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
        "messages": [],
        "created_at": None,
        "latency_ms": 0,
        "max_iterations": 5,
    }

    try:
        # ── Persist session ──
        await ctx.session_repo.create_session(session_id, request.user_id or "anonymous", request.query[:30])
        await ctx.session_repo.add_message(session_id, "user", request.query)

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
                state["query"] = f"{request.query}\n\n[图片描述: {image_context[:500]}]"
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
            # Stream RAG answer chunk by chunk
            async for chunk in generate_answer_stream(request.query, state["reranked_docs"], llm):
                yield f"data: {json.dumps({'type': 'answer', 'content': chunk, 'chunk': True})}\n\n"
        else:
            yield f"data: {json.dumps({'type': 'answer', 'content': state['answer'], 'chunk': False})}\n\n"

        # ── Step 4: Sources ──
        for i, source in enumerate(state.get("sources", [])):
            yield f"data: {json.dumps({'type': 'source', 'source': source, 'index': i})}\n\n"

        # ── Step 5: Evaluation ──
        if state["intent"] == "doc_qa" and state.get("reranked_docs"):
            state = await eval_node(state, llm=llm)
            yield f"data: {json.dumps({'type': 'evaluation', 'data': state['evaluation']})}\n\n"

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

    state = {
        "query": request.query,
        "session_id": session_id,
        "user_id": request.user_id or "anonymous",
        "knowledge_id": request.knowledge_id,
        "streaming": False,
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
        "messages": [],
        "created_at": None,
        "latency_ms": 0,
        "max_iterations": 5,
    }

    try:
        # ── Persist session ──
        await ctx.session_repo.create_session(session_id, request.user_id or "anonymous", request.query[:30])

        # ── Save user message ──
        await ctx.session_repo.add_message(session_id, "user", request.query)

        # ── Run agent graph ──
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
        raise HTTPException(status_code=500, detail=str(e))


# ── Session management endpoints ──

@router.get("/sessions")
async def list_sessions(user_id: str = "anonymous"):
    """List recent chat sessions."""
    sessions = await ctx.session_repo.list_sessions(user_id)
    return {"sessions": sessions}


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """Get a session with all messages."""
    session = await ctx.session_repo.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete (archive) a session."""
    success = await ctx.session_repo.delete_session(session_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete session")
    return {"status": "deleted", "session_id": session_id}
