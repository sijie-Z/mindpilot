"""
Answer generation agent with Self-RAG quality control.
Supports streaming and non-streaming modes, multiple intent routing.
"""
from collections.abc import AsyncGenerator
from typing import Any

from app.agents.state import AgentState
from app.core.llm_client import AsyncLLMClient
from app.core.logger import get_logger

logger = get_logger(__name__)


def build_rag_prompt(query: str, docs: list[dict[str, Any]], include_citation: bool = True) -> str:
    """Build RAG prompt with source citations."""
    doc_sections = []
    for i, doc in enumerate(docs):
        metadata = doc.get("metadata") or {}
        filename = metadata.get("filename", "未知")
        page = metadata.get("page", "?")

        if include_citation:
            doc_sections.append(
                f"【文档{i + 1}】来源: {filename} (第{page}页)\n{doc.get('content', '')}"
            )
        else:
            doc_sections.append(f"{i + 1}. {doc.get('content', '')}")

    context = "\n\n".join(doc_sections)

    return (
        f"基于以下文档内容回答用户问题。要求：\n"
        f"1. 准确引用文档内容，不要编造信息\n"
        f"2. 如果文档中没有相关信息，明确说明\n"
        f"3. 使用Markdown格式\n\n"
        f"参考文档：\n{context}\n\n"
        f"用户问题：{query}\n\n"
        f"请回答："
    )


async def generate_answer_stream(
    query: str,
    docs: list[dict[str, Any]],
    llm: AsyncLLMClient,
    enable_self_rag: bool = True,
) -> AsyncGenerator[str, None]:
    """Generate answer with SSE-compatible streaming."""
    if enable_self_rag and docs:
        try:
            from app.agents.self_rag import SelfRAG
            self_rag = SelfRAG(llm)
            is_relevant, score = await self_rag.check_relevance(query, docs)
            if not is_relevant:
                yield "[提示] 知识库中相关文档较少，以下内容仅供参考...\n\n"
        except Exception as e:
            logger.warning("Self-RAG relevance check failed in stream", error=str(e))

    prompt = build_rag_prompt(query, docs)
    async for chunk in llm.chat_stream(
        messages=[{"role": "user", "content": prompt}],
    ):
        yield chunk


async def generate_answer(
    query: str,
    docs: list[dict[str, Any]],
    llm: AsyncLLMClient,
    enable_self_rag: bool = True,
) -> dict[str, Any]:
    """Generate answer with optional Self-RAG quality control."""
    if not docs or not enable_self_rag:
        prompt = build_rag_prompt(query, docs) if docs else query
        answer = await llm.chat(messages=[{"role": "user", "content": prompt}])
        return {"answer": answer, "quality": {"relevance": 1.0, "faithfulness": 1.0}}

    try:
        from app.agents.self_rag import SelfRAG
        self_rag = SelfRAG(llm)

        prompt = build_rag_prompt(query, docs)
        from app.config import settings
        answer = await llm.chat(messages=[{"role": "user", "content": prompt}], model=settings.LLM_MODEL)
        result = await self_rag.evaluate_and_correct(query, answer, docs)
        return {
            "answer": result["final_answer"],
            "quality": {
                "relevance": result["relevance"]["score"],
                "faithfulness": result["faithfulness"]["score"],
                "corrected": result["corrected"],
            },
        }
    except Exception as e:
        logger.error("Self-RAG pipeline failed, falling back to simple answer", error=str(e))
        prompt = build_rag_prompt(query, docs)
        answer = await llm.chat(messages=[{"role": "user", "content": prompt}])
        return {"answer": answer, "quality": {"relevance": 0.0, "faithfulness": 0.0}}


async def answer_node(state: AgentState, llm: AsyncLLMClient | None = None) -> AgentState:
    """Generate answer based on intent, with intent-based routing."""
    if llm is None:
        llm = AsyncLLMClient()

    query = state["query"]
    intent = state["intent"]
    answer = ""
    sources = state.get("sources", [])
    quality: dict[str, Any] = {}

    try:
        if intent == "doc_qa" and state.get("reranked_docs"):
            docs = state["reranked_docs"]

            # Self-RAG check
            from app.agents.self_rag import SelfRAG
            self_rag = SelfRAG(llm)
            is_relevant, rel_score = await self_rag.check_relevance(query, docs)

            if not is_relevant:
                answer = (
                    "抱歉，我在知识库中没有找到与您问题高度相关的内容。\n\n"
                    "**可能的原因：**\n"
                    "1. 知识库中可能没有相关文档\n"
                    "2. 问题表述与文档内容存在差异\n\n"
                    "**建议：**\n"
                    "1. 尝试用不同的关键词描述您的问题\n"
                    "2. 确认相关文档已上传到知识库\n"
                )
                quality = {"relevance": rel_score, "irrelevant": True}
            else:
                result = await generate_answer(query, docs, llm, enable_self_rag=True)
                answer = result["answer"]
                quality = result["quality"]

            # Build sources
            sources = []
            for doc in docs[:5]:
                metadata = doc.get("metadata") or {}
                sources.append({
                    "filename": metadata.get("filename", "未知"),
                    "page": metadata.get("page"),
                    "chunk_id": doc.get("chunk_id", ""),
                    "content": (doc.get("content") or "")[:150],
                    "score": doc.get("rerank_score", doc.get("score", 0)),
                })

        elif intent in ("search", "calculation", "image", "code", "analysis"):
            from app.skills.registry import registry
            skill = registry.get_for_intent(intent)
            if skill:
                result = await registry.execute(skill.name, query)
                answer = result.result if result.success else f"{skill.description}出错: {result.error}"
            else:
                answer = f"未找到处理 {intent} 的技能"

        else:
            # General chat
            from app.config import settings
            answer = await llm.chat(
                messages=[{"role": "user", "content": query}],
                model=settings.LLM_MODEL,
            )

    except Exception as e:
        logger.error("Answer generation failed", intent=intent, error=str(e))
        answer = "抱歉，生成回答时发生错误，请稍后重试。"

    logger.info("Answer generated", intent=intent, answer_len=len(answer), has_sources=len(sources) > 0)

    return {
        **state,
        "answer": answer,
        "sources": sources,
        "quality": quality,
        "status": "generating",
    }
