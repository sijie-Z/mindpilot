"""
FAISS vector store as a lightweight alternative to Milvus.
Useful for development and testing without Milvus.
"""
import json
from pathlib import Path
from typing import Any

import numpy as np

from app.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)


class FAISSVectorStore:
    """
    FAISS-based vector store for local development.
    Stores vectors in memory and persists to disk.
    """

    def __init__(self, persist_dir: str = "data/faiss"):
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)

        self._index = None
        self._id_map: dict[int, str] = {}  # index -> chunk_id
        self._metadata: dict[str, dict] = {}  # chunk_id -> metadata
        self._dimension = settings.EMBEDDING_DIM

        # Try to load existing index
        self._load()

    def _load(self):
        """Load index and metadata from disk."""
        import faiss

        index_path = self.persist_dir / "index.faiss"
        meta_path = self.persist_dir / "metadata.json"

        if index_path.exists():
            self._index = faiss.read_index(str(index_path))
            # Load metadata
            if meta_path.exists():
                with open(meta_path) as f:
                    data = json.load(f)
                    self._id_map = {int(k): v for k, v in data.get("id_map", {}).items()}
                    self._metadata = data.get("metadata", {})
        else:
            # Create new index with Inner Product (for cosine similarity after normalization)
            self._index = faiss.IndexFlatIP(self._dimension)

    def _save(self):
        """Save index and metadata to disk."""
        import faiss

        faiss.write_index(self._index, str(self.persist_dir / "index.faiss"))

        with open(self.persist_dir / "metadata.json", "w") as f:
            json.dump({
                "id_map": self._id_map,
                "metadata": self._metadata,
            }, f)

    def insert_vectors(
        self,
        chunk_ids: list[str],
        vectors: np.ndarray,
        knowledge_id: str = "",
    ) -> bool:
        """
        Insert vectors into FAISS index.

        Args:
            chunk_ids: List of chunk IDs
            vectors: numpy array of embeddings (will be normalized)
            knowledge_id: Knowledge base ID for filtering
        """
        import faiss

        try:
            # Ensure float32
            if vectors.dtype != np.float32:
                vectors = vectors.astype(np.float32)

            # Normalize for cosine similarity
            faiss.normalize_L2(vectors)

            # Add to index
            start_idx = self._index.ntotal
            self._index.add(vectors)

            # Update mappings
            for i, chunk_id in enumerate(chunk_ids):
                idx = start_idx + i
                self._id_map[idx] = chunk_id
                self._metadata[chunk_id] = {"knowledge_id": knowledge_id}

            # Persist
            self._save()

            return True

        except Exception as e:
            logger.error("FAISS insert error", error=str(e))
            return False

    def search(
        self,
        query_vector: list[float],
        knowledge_id: str = "",
        top_k: int = 100,
    ) -> list[tuple[str, float]]:
        """
        Search for similar vectors.

        Returns:
            List of (chunk_id, score) tuples sorted by score descending
        """
        import faiss

        try:
            # Convert query
            query = np.array([query_vector], dtype=np.float32)
            faiss.normalize_L2(query)

            # Search
            search_k = min(top_k * 2, self._index.ntotal)  # Get more for filtering
            distances, indices = self._index.search(query, max(search_k, 1))

            # Filter and collect results with scores
            results = []
            for idx, dist in zip(indices[0], distances[0], strict=False):
                if idx < 0:
                    continue
                chunk_id = self._id_map.get(int(idx))
                if not chunk_id:
                    continue
                if knowledge_id:
                    meta = self._metadata.get(chunk_id, {})
                    if meta.get("knowledge_id") != knowledge_id:
                        continue
                results.append((chunk_id, float(dist)))

            # Sort by score
            results.sort(key=lambda x: x[1], reverse=True)

            return results[:top_k]

        except Exception as e:
            logger.error("FAISS search error", error=str(e))
            return []

    def delete_vectors(self, chunk_ids: list[str]) -> bool:
        """
        Delete vectors by chunk_ids.
        Note: FAISS doesn't support direct deletion, so we mark as deleted.
        """
        try:
            for chunk_id in chunk_ids:
                if chunk_id in self._metadata:
                    del self._metadata[chunk_id]

            # Remove from id_map
            for idx, cid in list(self._id_map.items()):
                if cid in chunk_ids:
                    del self._id_map[idx]

            self._save()
            return True

        except Exception as e:
            logger.error("FAISS delete error", error=str(e))
            return False

    def get_stats(self) -> dict[str, Any]:
        """Get index statistics."""
        return {
            "total_vectors": self._index.ntotal if self._index else 0,
            "dimension": self._dimension,
            "metadata_count": len(self._metadata),
        }


# Global instance (use FAISS as default for local development)
faiss_store = FAISSVectorStore()
