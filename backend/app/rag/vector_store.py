"""
Milvus vector store with dual-write consistency support.
Stores vectors in Milvus, full text in MySQL.
"""
from typing import Any

from pymilvus import Collection, CollectionSchema, DataType, FieldSchema, connections, utility

from app.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)


class MilvusVectorStore:
    """
    Milvus vector store for fast similarity search.

    Design:
    - Vectors + IDs stored in Milvus (HNSW index for fast ANN search)
    - Full text content stored in MySQL (for reranking)
    - Chunk metadata also in MySQL

    Consistency: Insert MySQL first, then Milvus.
    Rollback: If Milvus insert fails, delete the MySQL record.
    """

    COLLECTION_NAME = "mindpilot_vectors"

    def __init__(self):
        self._connected = False
        self._collection: Collection | None = None

    def connect(self):
        """Connect to Milvus server."""
        try:
            connections.connect(
                alias="default",
                host=settings.MILVUS_HOST,
                port=settings.MILVUS_PORT,
            )
            self._connected = True
            self._ensure_collection()
            logger.info("Connected to Milvus", host=settings.MILVUS_HOST, port=settings.MILVUS_PORT)
        except Exception as e:
            logger.warning("Failed to connect to Milvus", error=str(e))
            self._connected = False

    def _ensure_collection(self):
        """Create collection with HNSW index if not exists."""
        if utility.has_collection(self.COLLECTION_NAME):
            self._collection = Collection(self.COLLECTION_NAME)
            return

        fields = [
            FieldSchema(
                name="chunk_id",
                dtype=DataType.VARCHAR,
                max_length=64,
                is_primary=True,
            ),
            FieldSchema(
                name="knowledge_id",
                dtype=DataType.VARCHAR,
                max_length=64,
            ),
            FieldSchema(
                name="embedding",
                dtype=DataType.FLOAT_VECTOR,
                dim=settings.EMBEDDING_DIM,
            ),
        ]

        schema = CollectionSchema(
            fields=fields,
            description="MindPilot document embeddings with HNSW index",
        )

        self._collection = Collection(
            name=self.COLLECTION_NAME,
            schema=schema,
        )

        # Create HNSW index for fast approximate nearest neighbor search
        index_params = {
            "metric_type": "COSINE",
            "index_type": "HNSW",
            "params": {"M": 16, "efConstruction": 256},
        }
        self._collection.create_index(
            field_name="embedding",
            index_params=index_params,
        )
        self._collection.flush()

    def insert_vectors(
        self,
        chunk_ids: list[str],
        embeddings: list[list[float]],
        knowledge_id: str = "",
    ) -> bool:
        """
        Insert vectors into Milvus (synchronous operation).
        Returns True if successful.
        """
        if not self._connected:
            self.connect()

        if not self._connected:
            return False

        try:
            knowledge_ids = [knowledge_id] * len(chunk_ids)

            entities = [
                chunk_ids,      # chunk_id field
                knowledge_ids,   # knowledge_id field
                embeddings,      # embedding field
            ]

            self._collection.insert(entities)
            self._collection.flush()
            return True

        except Exception as e:
            logger.error("Milvus insert error", error=str(e))
            return False

    def search(
        self,
        query_vector: list[float],
        knowledge_id: str = "",
        top_k: int = 100,
    ) -> list[tuple[str, float]]:
        """
        Search for similar vectors.
        Returns List of (chunk_id, distance) tuples sorted by distance descending.
        Uses COSINE similarity - distance 1.0 means perfect match.
        """
        if not self._connected:
            self.connect()

        if not self._connected:
            return []

        try:
            self._collection.load()

            search_params = {
                "metric_type": "COSINE",
                "params": {"ef": 64},
            }

            # Filter by knowledge_id if specified
            expr = f'knowledge_id == "{knowledge_id}"' if knowledge_id else ""

            results = self._collection.search(
                data=[query_vector],
                anns_field="embedding",
                param=search_params,
                limit=top_k,
                expr=expr,
                output_fields=["chunk_id"],
            )

            # Return (chunk_id, distance) tuples
            return [
                (hit.entity.get("chunk_id"), float(hit.distance))
                for hit in results[0]
            ]

        except Exception as e:
            logger.error("Milvus search error", error=str(e))
            return []

    def delete_vectors(self, chunk_ids: list[str]) -> bool:
        """Delete vectors by chunk_ids."""
        if not self._connected:
            self.connect()

        if not self._connected:
            return False

        try:
            expr = f'chunk_id in {chunk_ids}'
            self._collection.delete(expr)
            self._collection.flush()
            return True
        except Exception as e:
            logger.error("Milvus delete error", error=str(e))
            return False

    def get_stats(self) -> dict[str, Any]:
        """Get collection statistics."""
        if not self._connected:
            return {"connected": False}

        try:
            stats = self._collection.num_entities
            return {
                "connected": True,
                "total_vectors": stats,
                "collection": self.COLLECTION_NAME,
            }
        except Exception:
            return {"connected": False}


# Global instance
vector_store = MilvusVectorStore()
