"""
Hybrid retriever supporting both Milvus and FAISS.
Dynamic weight adjustment for vector + BM25 hybrid search.
"""
import logging
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)


def get_vector_store():
    """Get the configured vector store (Milvus or FAISS)."""
    if settings.VECTOR_STORE == "milvus":
        from app.rag.vector_store import vector_store
        return vector_store
    else:
        from app.rag.faiss_store import faiss_store
        return faiss_store


class HybridRetriever:
    """
    Hybrid retriever combining dense vector search + sparse BM25.

    Design:
    - Vector search: Milvus (HNSW index) or FAISS (local fallback)
    - BM25 search: MySQL ngram fulltext index
    - Fusion: Reciprocal Rank Fusion (RRF)
    - Rerank: fetch content from MySQL, re-score with multiple signals

    The weight slider in frontend controls vector_weight vs bm25_weight.
    """

    def __init__(
        self,
        vector_weight: float = None,
        bm25_weight: float = None,
    ):
        self.vector_weight = vector_weight or settings.DEFAULT_VECTOR_WEIGHT
        self.bm25_weight = bm25_weight or settings.DEFAULT_BM25_WEIGHT
        self._vector_store = get_vector_store()

    def set_weights(self, vector_weight: float, bm25_weight: float):
        """Update retrieval weights from frontend slider."""
        self.vector_weight = vector_weight
        self.bm25_weight = bm25_weight

    async def search(
        self,
        query: str,
        knowledge_id: str = "",
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Hybrid search pipeline:
        1. Query embedding via Zhipu
        2. Vector search (Milvus/FAISS)
        3. BM25 via MySQL ngram
        4. RRF fusion
        5. Fetch content from MySQL for reranking
        """
        from app.rag.embedder import embedder

        # Step 1: Get query embedding
        query_embedding = await embedder.embed_query(query)

        # Step 2: Vector search (run sync Milvus in thread pool)
        import asyncio
        vector_results = await asyncio.to_thread(
            self._vector_store.search,
            query_vector=query_embedding,
            knowledge_id=knowledge_id,
            top_k=100,
        )

        # Handle both formats: (chunk_id, score) tuples or just chunk_ids
        if vector_results and isinstance(vector_results[0], tuple):
            # Milvus format: (chunk_id, distance)
            vector_ids = [(cid, score) for cid, score in vector_results]
        else:
            # FAISS format: just chunk_ids
            vector_ids = [(cid, 1.0 - i * 0.01) for i, cid in enumerate(vector_results)]

        # Step 3: BM25 search via MySQL
        bm25_ids = await self._bm25_search(query, knowledge_id)

        # Step 4: RRF fusion
        fused = self._rrf_fusion(vector_ids, bm25_ids)

        # Step 5: Fetch content from MySQL
        fused_ids = [chunk_id for chunk_id, _ in fused]
        results = await self._get_chunks_from_mysql(fused_ids)

        # Step 6: Add scores
        score_map = dict(fused)
        for r in results:
            r["score"] = score_map.get(r["chunk_id"], 0.0)

        return results[:top_k]

    async def _bm25_search(
        self,
        query: str,
        knowledge_id: str = "",
        limit: int = 20,
    ) -> list[str]:
        """
        BM25 search using MySQL fulltext index with ngram parser.
        Supports Chinese tokenization.
        """
        try:
            from sqlalchemy import text

            from app.storage.database import get_db_session

            async with get_db_session() as db:
                if knowledge_id:
                    result = await db.execute(
                        text("SELECT c.id FROM chunks c "
                             "JOIN documents d ON c.doc_id = d.id "
                             "WHERE MATCH(c.content) AGAINST(:query IN NATURAL LANGUAGE MODE) "
                             "AND d.knowledge_id = :kid LIMIT :lim"),
                        {"query": query, "kid": knowledge_id, "lim": limit}
                    )
                else:
                    result = await db.execute(
                        text("SELECT id FROM chunks WHERE MATCH(content) "
                             "AGAINST(:query IN NATURAL LANGUAGE MODE) LIMIT :lim"),
                        {"query": query, "lim": limit}
                    )
                return [row[0] for row in result.fetchall()]
        except Exception as e:
            logger.debug(f"BM25 search skipped (fulltext not ready): {e}")
            return []

    def _rrf_fusion(
        self,
        vector_results: list[tuple[str, float]],
        bm25_results: list[str],
        k: int = 60,
    ) -> list[tuple[str, float]]:
        """
        Reciprocal Rank Fusion algorithm.

        Merges ranked lists from vector search and BM25.
        RRF score = Σ (weight / (rank + k))

        k=60 is standard, prevents division by zero.
        """
        scores = {}

        # Vector search results (already scored)
        for chunk_id, vec_score in vector_results:
            scores[chunk_id] = scores.get(chunk_id, 0) + (
                self.vector_weight * vec_score / (1 + k)
            )

        # BM25 results (rank-based scoring)
        for rank, chunk_id in enumerate(bm25_results):
            scores[chunk_id] = scores.get(chunk_id, 0) + (
                self.bm25_weight / (rank + k)
            )

        # Sort by fused score descending
        sorted_results = sorted(
            scores.items(),
            key=lambda x: x[1],
            reverse=True,
        )

        return sorted_results

    async def _get_chunks_from_mysql(
        self,
        chunk_ids: list[str],
    ) -> list[dict[str, Any]]:
        """Fetch chunk content from MySQL for reranking."""
        if not chunk_ids:
            return []

        try:
            from sqlalchemy import text

            from app.storage.database import get_db_session

            async with get_db_session() as db:
                placeholders = ", ".join([f":id_{i}" for i in range(len(chunk_ids))])
                params = {f"id_{i}": id_val for i, id_val in enumerate(chunk_ids)}
                result = await db.execute(
                    text(f"SELECT id, content, metadata FROM chunks WHERE id IN ({placeholders})"),
                    params
                )
                rows = result.fetchall()

                return [
                    {
                        "chunk_id": row[0],
                        "content": row[1],
                        "metadata": row[2] if isinstance(row[2], dict) else {},
                    }
                    for row in rows
                ]
        except Exception:
            return []

    def get_stats(self) -> dict[str, Any]:
        """Get vector store stats."""
        if hasattr(self._vector_store, 'get_stats'):
            return self._vector_store.get_stats()
        return {"type": settings.VECTOR_STORE}


# Global instance
retriever = HybridRetriever()


async def reload_retriever():
    """Reload retriever when config changes."""
    global retriever
    retriever = HybridRetriever()
