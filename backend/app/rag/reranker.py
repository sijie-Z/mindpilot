"""
Reranker module for improved relevance ranking.
Uses multi-signal scoring (BM25 + vector + position + length) with optional LLM boost.
"""
import json
from typing import Any

from app.core.llm_client import AsyncLLMClient
from app.core.logger import get_logger

logger = get_logger(__name__)


class Reranker:
    """
    Multi-signal reranker: BM25, vector similarity, position, length.

    When use_llm is enabled, LLM scoring replaces heuristic scoring
    for top-N precision (slower but more accurate).
    """

    def __init__(
        self,
        vector_weight: float = 0.4,
        bm25_weight: float = 0.3,
        position_weight: float = 0.2,
        length_penalty_weight: float = 0.1,
        top_k: int = 5,
    ):
        self.vector_weight = vector_weight
        self.bm25_weight = bm25_weight
        self.position_weight = position_weight
        self.length_penalty_weight = length_penalty_weight
        self.top_k = top_k

    def calculate_bm25_score(self, query: str, text: str) -> float:
        """Calculate simple BM25-style term overlap score."""
        query_terms = set(query.lower().split())
        text_lower = text.lower()
        if not query_terms:
            return 0.0
        matches = sum(1 for term in query_terms if term in text_lower)
        tf = matches / max(len(text_lower.split()), 1)
        idf = 1.0 / (1 + matches * 0.1)
        return tf * idf

    def calculate_length_penalty(self, text: str, ideal_length: int = 300) -> float:
        """Penalize chunks that are too short or too long."""
        length = len(text)
        if length < 50:
            return 0.5
        if length > 1000:
            return 0.7
        deviation = abs(length - ideal_length) / ideal_length
        return max(0.5, 1.0 - deviation * 0.3)

    def calculate_position_score(self, index: int, total: int) -> float:
        """Earlier results get higher position scores."""
        if total <= 1:
            return 1.0
        return 1.0 - ((index / total) * 0.5)

    async def rerank(
        self,
        query: str,
        docs: list[dict[str, Any]],
        vector_scores: list[float] = None,
    ) -> list[dict[str, Any]]:
        """Multi-signal heuristic reranking."""
        if not docs:
            return []

        scored_docs = []
        for i, doc in enumerate(docs):
            content = doc.get("content") or doc.get("chunk_text") or ""
            bm25_score = self.calculate_bm25_score(query, content)
            vec_score = vector_scores[i] if vector_scores and i < len(vector_scores) else 0.5
            position_score = self.calculate_position_score(i, len(docs))
            length_score = self.calculate_length_penalty(content)

            final_score = (
                self.vector_weight * vec_score
                + self.bm25_weight * bm25_score * 2
                + self.position_weight * position_score
                + self.length_penalty_weight * length_score
            )
            final_score = min(1.0, max(0.0, final_score))

            scored_docs.append({
                **doc,
                "rerank_score": final_score,
                "score_breakdown": {
                    "vector_score": vec_score,
                    "bm25_score": bm25_score,
                    "position_score": position_score,
                    "length_score": length_score,
                },
            })

        scored_docs.sort(key=lambda x: x["rerank_score"], reverse=True)
        return scored_docs[:self.top_k]

    async def rerank_with_llm(
        self,
        query: str,
        docs: list[dict[str, Any]],
        llm: AsyncLLMClient | None = None,
    ) -> list[dict[str, Any]]:
        """LLM-based reranking for top-N precision. Falls back to heuristic on failure."""
        if llm is None:
            llm = AsyncLLMClient()

        try:
            doc_texts = [
                f"[{i + 1}] {(doc.get('content') or '')[:500]}"
                for i, doc in enumerate(docs[:10])
            ]

            prompt = (
                f"评估以下文档与查询的相关性。\n\n"
                f"查询: {query}\n\n"
                f"文档:\n{chr(10).join(doc_texts)}\n\n"
                f"为每个文档评分(0-10)，只输出JSON数组如: [8, 5, 3, 9, 2]"
            )

            result = await llm.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=50,
            )

            if "[" in result:
                start = result.index("[")
                end = result.index("]") + 1
                scores = json.loads(result[start:end])

                for i, doc in enumerate(docs[:len(scores)]):
                    doc["rerank_score"] = scores[i] / 10.0
                    doc["rerank_method"] = "llm"

                scored = sorted(
                    [d for d in docs[:len(scores)] if "rerank_score" in d],
                    key=lambda x: x["rerank_score"],
                    reverse=True,
                )
                scored.extend(docs[len(scores):])
                return scored[:self.top_k]

        except Exception as e:
            logger.warning("LLM reranking failed, using heuristic", error=str(e))

        return await self.rerank(query, docs)


# Global instance
reranker = Reranker()


async def rerank_documents(
    query: str,
    docs: list[dict[str, Any]],
    vector_scores: list[float] = None,
    use_llm: bool = False,
    llm: AsyncLLMClient | None = None,
) -> list[dict[str, Any]]:
    """Convenience function to rerank documents."""
    if use_llm:
        return await reranker.rerank_with_llm(query, docs, llm=llm)
    return await reranker.rerank(query, docs, vector_scores)
