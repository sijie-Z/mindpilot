"""
Evaluation agent using LLM-based RAGAS-like metrics.
Replaces heuristic string matching with real LLM-as-judge evaluation.
"""
from datetime import UTC, datetime
from typing import Any

from app.agents.state import AgentState
from app.core.llm_client import AsyncLLMClient
from app.core.logger import get_logger

logger = get_logger(__name__)

# Quality threshold for triggering retrieval retry
QUALITY_RETRY_THRESHOLD = 0.5
MAX_RETRIEVAL_ATTEMPTS = 2

# ── Metric prompts ──

ANSWER_RELEVANCY_PROMPT = """评估生成答案与用户问题的相关性。

用户问题: {query}
生成答案: {answer}

请给出0-1的评分，其中：
- 1.0: 答案完全切题，直接回应用户问题
- 0.7-0.9: 答案基本相关，但部分内容偏离主题
- 0.4-0.6: 答案部分相关，但包含大量无关内容
- 0.0-0.3: 答案基本不相关

返回JSON格式: {{"score": 0.0, "reason": "评分理由"}}"""

FAITHFULNESS_PROMPT = """评估生成答案是否忠实于参考文档（即回答中的声明是否都能在文档中找到依据）。

参考文档:
{documents}

用户问题: {query}

生成答案: {answer}

请给出0-1的评分，其中：
- 1.0: 所有声明都能在文档中找到依据
- 0.7-0.9: 大部分声明有依据，少量合理推断
- 0.4-0.6: 部分声明无文档支持
- 0.0-0.3: 大量捏造/幻觉内容

返回JSON格式: {{"score": 0.0, "reason": "评分理由", "hallucinated": "捏造的内容（如有）"}}"""

CONTEXT_PRECISION_PROMPT = """评估检索到的文档片段对回答用户问题是否有用。

用户问题: {query}

检索到的文档片段:
{documents}

请给出0-1的评分，其中：
- 1.0: 所有文档片段都与问题高度相关
- 0.7-0.9: 大部分文档相关
- 0.4-0.6: 部分文档相关
- 0.0-0.3: 大部分文档无关

返回JSON格式: {{"score": 0.0, "reason": "评分理由"}}"""


async def llm_score(prompt: str, llm: AsyncLLMClient) -> float:
    """Get a 0-1 score from LLM judge. Returns 0.5 as safe default on failure."""
    try:
        result = await llm.chat_json(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )
        score = float(result.get("score", 0.5))
        return max(0.0, min(1.0, score))
    except Exception as e:
        logger.warning("LLM scoring failed, using default", error=str(e))
        return 0.5


async def evaluate_answer_relevance(query: str, answer: str, llm: AsyncLLMClient) -> dict[str, Any]:
    """LLM-based answer relevance evaluation."""
    if not answer or len(answer) < 10:
        return {"score": 0.2, "reason": "Answer too short"}

    prompt = ANSWER_RELEVANCY_PROMPT.format(query=query, answer=answer[:2000])
    score = await llm_score(prompt, llm)
    return {"score": score}


async def evaluate_faithfulness(
    query: str, answer: str, docs: list, llm: AsyncLLMClient
) -> dict[str, Any]:
    """LLM-based faithfulness evaluation against source documents."""
    if not docs or not answer:
        return {"score": 0.5}

    doc_texts = []
    for i, doc in enumerate(docs[:3]):
        content = (doc.get("content") or "")[:500]
        doc_texts.append(f"[文档{i + 1}]: {content}")

    prompt = FAITHFULNESS_PROMPT.format(
        documents="\n".join(doc_texts),
        query=query,
        answer=answer[:2000],
    )
    score = await llm_score(prompt, llm)
    return {"score": score}


async def evaluate_context_precision(
    query: str, docs: list, llm: AsyncLLMClient
) -> dict[str, Any]:
    """LLM-based context precision evaluation."""
    if not docs:
        return {"score": 0.0}

    doc_texts = []
    for i, doc in enumerate(docs[:5]):
        content = (doc.get("content") or "")[:300]
        score = doc.get("rerank_score", doc.get("score", 0))
        doc_texts.append(f"[文档{i + 1}] (检索分: {score:.2f}): {content}")

    prompt = CONTEXT_PRECISION_PROMPT.format(
        query=query,
        documents="\n".join(doc_texts),
    )
    score = await llm_score(prompt, llm)
    return {"score": score}


async def eval_node(state: AgentState, llm: AsyncLLMClient | None = None) -> AgentState:
    """
    Evaluate generated answer quality using LLM-as-judge metrics.
    Sets quality_passed=False if answer quality is below threshold,
    which triggers the retry loop in the graph.
    """
    if llm is None:
        llm = AsyncLLMClient()

    query = state["query"]
    answer = state.get("answer", "")
    docs = state.get("reranked_docs", [])
    intent = state.get("intent", "general")

    # Skip evaluation for non-doc_qa intents
    if intent != "doc_qa" or not docs:
        return {
            **state,
            "evaluation": {"overall": 1.0, "skipped": True},
            "quality_passed": True,
            "status": "done",
        }

    logger.info("Running LLM-based evaluation", query=query[:60])

    # Run evaluations in parallel
    import asyncio
    relevance_future = evaluate_answer_relevance(query, answer, llm)
    faithfulness_future = evaluate_faithfulness(query, answer, docs, llm)
    precision_future = evaluate_context_precision(query, docs, llm)

    relevance, faithfulness, precision = await asyncio.gather(
        relevance_future, faithfulness_future, precision_future,
    )

    answer_rel = relevance.get("score", 0.5)
    faith = faithfulness.get("score", 0.5)
    ctx_prec = precision.get("score", 0.5)

    # Weighted overall: faithfulness is most important
    overall = round(answer_rel * 0.3 + faith * 0.4 + ctx_prec * 0.3, 3)

    # Incorporate Self-RAG quality if available
    quality = state.get("quality", {})
    if quality.get("relevance"):
        answer_rel = max(answer_rel, float(quality["relevance"]) * 0.8)
    if quality.get("faithfulness"):
        faith = max(faith, float(quality["faithfulness"]) * 0.8)

    evaluation = {
        "answer_relevance": answer_rel,
        "faithfulness": faith,
        "context_precision": ctx_prec,
        "overall": overall,
    }

    # ── Quality gate: should we retry? ──
    retrieval_attempts = state.get("retrieval_attempts", 0)
    quality_passed = True
    quality_feedback = ""

    if overall < QUALITY_RETRY_THRESHOLD and retrieval_attempts < MAX_RETRIEVAL_ATTEMPTS:
        quality_passed = False
        # Generate feedback for query rewriting
        try:
            feedback_prompt = f"""回答质量评分较低(总分: {overall})。
相关性: {answer_rel}, 忠实度: {faith}, 检索精度: {ctx_prec}

请用一句话说明应该如何改进检索或回答，直接输出建议。"""
            quality_feedback = await llm.chat(
                messages=[{"role": "user", "content": feedback_prompt}],
                temperature=0.3,
                max_tokens=100,
            )
        except Exception:
            quality_feedback = "检索结果不够精准，需要扩展搜索范围"
        logger.info("Quality below threshold, triggering retry", overall=overall, feedback=quality_feedback)

    # Calculate latency
    created_at = state.get("created_at")
    latency_ms = 0
    if created_at:
        latency_ms = int((datetime.now(UTC) - created_at).total_seconds() * 1000)
    evaluation["latency_ms"] = latency_ms

    logger.info("Evaluation complete", **evaluation)

    return {
        **state,
        "evaluation": evaluation,
        "quality_passed": quality_passed,
        "quality_feedback": quality_feedback,
        "status": "done",
    }
