"""
Retrieval agent with hybrid search, query expansion, and reranking.
Orchestrates the full retrieval pipeline: expand → search → fuse → rerank.
"""

from app.agents.state import AgentState
from app.core.llm_client import AsyncLLMClient
from app.core.logger import get_logger

logger = get_logger(__name__)


async def expand_query(query: str, llm: AsyncLLMClient) -> list[str]:
    """Generate query variants to improve recall."""
    try:
        result = await llm.chat(
            messages=[{
                "role": "user",
                "content": (
                    f"将用户问题改写成3个不同角度的搜索关键词/短句，保持核心语义。\n"
                    f"用户问题：「{query}」\n"
                    f"直接返回关键词，每行一个，不要编号和解释。"
                ),
            }],
            temperature=0.3,
            max_tokens=200,
        )
        keywords = [line.strip() for line in result.split("\n") if line.strip()]
        logger.debug("Query expanded", original=query, expanded=keywords[:3])
        return keywords[:3] if keywords else [query]
    except Exception as e:
        logger.warning("Query expansion failed", error=str(e))
        return [query]


async def retrieval_node(state: AgentState, llm: AsyncLLMClient | None = None) -> AgentState:
    """
    Hybrid retrieval pipeline:
    1. Query expansion via LLM
    2. Vector + BM25 hybrid search via RRF fusion
    3. LLM-based reranking
    """
    if llm is None:
        llm = AsyncLLMClient()

    query = state["query"]
    intent = state["intent"]
    knowledge_id = state.get("knowledge_id", "")

    # ── Non-doc_qa intents skip retrieval entirely ──
    if intent != "doc_qa":
        logger.info("Skipping retrieval for non-doc_qa intent", intent=intent)
        return {
            **state,
            "retrieved_docs": [],
            "reranked_docs": [],
            "expanded_queries": [],
        }

    retrieval_attempts = state.get("retrieval_attempts", 0)
    logger.info("Retrieval started", query=query[:80], attempt=retrieval_attempts + 1)

    # ── Step 1: Query expansion ──
    quality_feedback = state.get("quality_feedback", "")
    search_query = query
    if quality_feedback:
        search_query = f"{query} ({quality_feedback})"

    expanded_queries = await expand_query(search_query, llm)

    # ── Step 2: Hybrid retrieval ──
    retrieved_docs = []
    try:
        from app.rag.retriever import retriever
        retrieved_docs = await retriever.search(
            query=query,
            knowledge_id=knowledge_id,
            top_k=20,
        )
        logger.info("Hybrid retrieval completed", count=len(retrieved_docs))
    except Exception as e:
        logger.error("Hybrid retrieval failed", error=str(e))

    # ── Step 3: Rerank ──
    reranked_docs = retrieved_docs
    try:
        from app.rag.reranker import rerank_documents
        if retrieved_docs:
            vector_scores = [doc.get("score", 0.0) for doc in retrieved_docs]
            reranked_docs = await rerank_documents(
                query=query,
                docs=retrieved_docs,
                vector_scores=vector_scores,
                use_llm=True,
            )
            logger.info("Reranking completed", top_n=len(reranked_docs))
    except Exception as e:
        logger.error("Reranking failed, using raw results", error=str(e))
        reranked_docs = sorted(retrieved_docs, key=lambda x: x.get("score", 0), reverse=True)[:5]

    # ── Build sources ──
    sources = []
    for doc in reranked_docs[:5]:
        metadata = doc.get("metadata") or {}
        sources.append({
            "chunk_id": doc.get("chunk_id", ""),
            "filename": metadata.get("filename", ""),
            "content": (doc.get("content") or "")[:200],
            "score": doc.get("rerank_score", doc.get("score", 0)),
        })

    return {
        **state,
        "expanded_queries": expanded_queries,
        "retrieved_docs": retrieved_docs,
        "reranked_docs": reranked_docs,
        "sources": sources,
        "retrieval_attempts": retrieval_attempts + 1,
    }
