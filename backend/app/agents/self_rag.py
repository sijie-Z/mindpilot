"""
Self-RAG: Retrieve → Generate → Critique → Correct loop.
Checks relevance and faithfulness, self-corrects when needed.
"""
from typing import Any

from app.core.llm_client import AsyncLLMClient
from app.core.logger import get_logger

logger = get_logger(__name__)


class SelfRAG:
    """
    Self-RAG quality control: relevance check → faithfulness check → self-correction.
    Uses LLM-as-judge for all checks.
    """

    def __init__(self, llm: AsyncLLMClient):
        self.llm = llm
        self.max_retries = 2

    async def check_relevance(
        self, query: str, docs: list[dict[str, Any]]
    ) -> tuple[bool, float]:
        """Check if retrieved documents are relevant to the query."""
        if not docs:
            return False, 0.0

        # Fast keyword pre-check
        query_terms = set(query.lower().split())
        if query_terms:
            keyword_scores = []
            for doc in docs[:5]:
                content = (doc.get("content") or doc.get("chunk_text", "")).lower()
                matches = sum(1 for t in query_terms if t in content)
                keyword_scores.append(matches / max(len(query_terms), 1))
            avg_keyword = sum(keyword_scores) / max(len(keyword_scores), 1)
            if avg_keyword >= 0.3:
                return True, avg_keyword

        # LLM deep check
        return await self._llm_relevance_check(query, docs)

    async def _llm_relevance_check(
        self, query: str, docs: list[dict[str, Any]]
    ) -> tuple[bool, float]:
        """LLM-based relevance check."""
        doc_summaries = []
        for i, doc in enumerate(docs[:5]):
            content = (doc.get("content") or "")[:300]
            doc_summaries.append(f"[文档{i + 1}]: {content}")

        try:
            result = await self.llm.chat_json(
                messages=[{
                    "role": "user",
                    "content": (
                        f"判断以下文档是否与用户问题相关。\n\n"
                        f"用户问题: {query}\n\n"
                        f"文档内容:\n{chr(10).join(doc_summaries)}\n\n"
                        f'返回JSON: {{"relevant": true/false, "score": 0.0-1.0}}'
                    ),
                }],
                temperature=0.1,
            )
            return result.get("relevant", False), result.get("score", 0.0)
        except Exception as e:
            logger.warning("LLM relevance check failed", error=str(e))
            return False, 0.0

    async def check_faithfulness(
        self, query: str, answer: str, docs: list[dict[str, Any]]
    ) -> tuple[bool, float]:
        """Check if answer is faithful to source documents."""
        doc_texts = []
        for i, doc in enumerate(docs[:3]):
            content = (doc.get("content") or "")[:500]
            doc_texts.append(f"[文档{i + 1}]: {content}")

        try:
            result = await self.llm.chat_json(
                messages=[{
                    "role": "user",
                    "content": (
                        f"评估回答是否忠实于参考文档。\n\n"
                        f"参考文档:\n{chr(10).join(doc_texts)}\n\n"
                        f"用户问题: {query}\n\n"
                        f"回答: {answer}\n\n"
                        f'返回JSON: {{"faithful": true/false, "score": 0.0-1.0, '
                        f'"hallucinated_parts": "捏造的部分（如有）"}}'
                    ),
                }],
                temperature=0.1,
            )
            return result.get("faithful", True), result.get("score", 1.0)
        except Exception as e:
            logger.warning("Faithfulness check failed", error=str(e))
            return True, 1.0

    async def should_retrieve(self, query: str, intent: str) -> tuple[bool, str]:
        """Decide if retrieval is needed."""
        if intent == "doc_qa":
            return True, "文档问答需要检索"
        if intent in ("calculation", "code", "general"):
            return False, f"{intent}不需文档检索"
        if intent == "search":
            return True, "搜索类问题需要检索"

        # Fallback LLM decision
        try:
            result = await self.llm.chat_json(
                messages=[{
                    "role": "user",
                    "content": (
                        f"判断是否需要从知识库检索文档才能回答。\n"
                        f"问题: {query}\n"
                        f'返回JSON: {{"needs_retrieval": true/false, "reason": "..."}}'
                    ),
                }],
                temperature=0.1,
            )
            return result.get("needs_retrieval", False), result.get("reason", "")
        except Exception:
            return False, "默认不检索"

    async def self_correct(
        self, query: str, answer: str, docs: list[dict[str, Any]], issues: str
    ) -> str:
        """Generate corrected answer based on identified issues."""
        doc_texts = []
        for i, doc in enumerate(docs[:3]):
            content = (doc.get("content") or "")[:500]
            doc_texts.append(f"[文档{i + 1}]: {content}")

        try:
            return await self.llm.chat(
                messages=[{
                    "role": "user",
                    "content": (
                        f"之前的回答存在问题: {issues}\n\n"
                        f"请基于参考文档重新回答，确保完全基于文档内容。\n\n"
                        f"参考文档:\n{chr(10).join(doc_texts)}\n\n"
                        f"用户问题: {query}\n\n请重新回答:"
                    ),
                }],
                model="glm-4",
                temperature=0.3,
                max_tokens=1000,
            )
        except Exception as e:
            logger.error("Self-correction failed", error=str(e))
            return answer

    async def evaluate_and_correct(
        self, query: str, answer: str, docs: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Full Self-RAG pipeline: check → correct → verify."""
        result: dict[str, Any] = {
            "relevance": {"score": 0.0, "passed": False},
            "faithfulness": {"score": 1.0, "passed": True},
            "corrected": False,
            "final_answer": answer,
        }

        # Step 1: Check relevance
        is_relevant, rel_score = await self.check_relevance(query, docs)
        result["relevance"] = {"score": rel_score, "passed": is_relevant}

        if not is_relevant:
            result["final_answer"] = (
                "抱歉，我在知识库中没有找到与您问题相关的内容。\n\n"
                "您可以尝试：\n"
                "1. 换一种方式描述您的问题\n"
                "2. 确认相关文档已上传到知识库\n"
                "3. 联系管理员添加更多相关资料"
            )
            return result

        # Step 2: Check faithfulness
        is_faithful, faith_score = await self.check_faithfulness(query, answer, docs)
        result["faithfulness"] = {"score": faith_score, "passed": is_faithful}

        # Step 3: Self-correct if needed
        if not is_faithful and docs:
            corrected = await self.self_correct(
                query, answer, docs,
                f"回答忠实度不足(分数: {faith_score:.2f})，可能包含文档中没有的信息",
            )
            result["final_answer"] = corrected
            result["corrected"] = True
            logger.info("Self-RAG corrected answer", original_len=len(answer), corrected_len=len(corrected))

        return result
