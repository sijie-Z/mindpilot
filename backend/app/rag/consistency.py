"""
Data consistency manager for MySQL + Milvus dual-write.
Ensures atomicity: MySQL first, Milvus second, rollback on failure.
"""
import asyncio
import json
from typing import Any

from sqlalchemy import text

from app.core.logger import get_logger

logger = get_logger(__name__)


class DataConsistencyManager:
    """
    MySQL + Milvus dual-write consistency manager.

    Strategy:
    - Insert: MySQL first, then Milvus. Rollback MySQL if Milvus fails.
    - Delete: Double-delete - delete from both stores.
    - Search: Vector search from Milvus, content from MySQL.
    """

    def __init__(self):
        self._mysql_ok = False
        self._milvus_ok = False

    async def insert_chunks_with_rollback(
        self,
        chunks: list[dict[str, Any]],
        embeddings: list[list[float]],
        knowledge_id: str = "",
        doc_id: str = "",
    ) -> bool:
        """
        Insert chunks with rollback mechanism.

        Step 1: Write text + metadata to MySQL
        Step 2: Write vectors to Milvus
        Step 3: If Milvus fails, rollback MySQL insert

        Returns True if both succeed.
        """
        from app.storage.database import get_db_session

        chunk_ids = [c["id"] for c in chunks]

        # Step 1: Insert into MySQL first
        inserted_ids = []
        try:
            async with get_db_session() as db:
                for chunk in chunks:
                    await db.execute(
                        text("INSERT INTO chunks (id, doc_id, chunk_index, content, metadata) "
                             "VALUES (:id, :doc_id, :idx, :content, :metadata)"),
                        {
                            "id": chunk["id"],
                            "doc_id": doc_id,
                            "idx": chunk["chunk_index"],
                            "content": chunk["content"],
                            "metadata": json.dumps(chunk.get("metadata", {}), ensure_ascii=False)
                        }
                    )
                    inserted_ids.append(chunk["id"])
            logger.info(f"MySQL insert success: {len(inserted_ids)} chunks")
            self._mysql_ok = True

        except Exception as e:
            logger.error(f"MySQL insert failed: {e}")
            return False

        # Step 2: Insert vectors into Milvus (sync operation, run in thread)
        try:
            from app.rag.vector_store import vector_store

            success = await asyncio.to_thread(
                vector_store.insert_vectors,
                chunk_ids=chunk_ids,
                embeddings=embeddings,
                knowledge_id=knowledge_id,
            )

            if success:
                logger.info(f"Milvus insert success: {len(chunk_ids)} vectors")
                self._milvus_ok = True
                return True
            else:
                raise Exception("Milvus insert returned False")

        except Exception as e:
            logger.error(f"Milvus insert failed: {e}, rolling back MySQL")

            # Step 3: Rollback MySQL
            try:
                async with get_db_session() as db:
                    # Use multiple separate conditions for IN clause
                    placeholders = ", ".join([f":id_{i}" for i in range(len(inserted_ids))])
                    params = {f"id_{i}": id_val for i, id_val in enumerate(inserted_ids)}
                    await db.execute(
                        text(f"DELETE FROM chunks WHERE id IN ({placeholders})"),
                        params
                    )
                logger.info(f"Rollback success: deleted {len(inserted_ids)} chunks from MySQL")
            except Exception as rollback_err:
                logger.error(f"Rollback also failed: {rollback_err}")

            return False

    async def delete_document_with_rollback(
        self,
        doc_id: str,
    ) -> bool:
        """
        Delete document with double-delete strategy.

        Step 1: Get all chunk IDss
        Step 2: Delete from MySQL
        Step 3: Delete from Milvus (sync operation, run in thread)
        """
        from app.storage.database import get_db_session

        # Step 1: Get chunk IDs
        try:
            async with get_db_session() as db:
                result = await db.execute(
                    text("SELECT id FROM chunks WHERE doc_id=:doc_id"),
                    {"doc_id": doc_id}
                )
                chunk_ids = [row[0] for row in result.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get chunk IDs: {e}")
            return False

        if not chunk_ids:
            logger.info(f"No chunks found for doc {doc_id}")
            return True

        # Step 2: Delete from MySQL
        try:
            async with get_db_session() as db:
                placeholders = ", ".join([f":id_{i}" for i in range(len(chunk_ids))])
                params = {f"id_{i}": id_val for i, id_val in enumerate(chunk_ids)}
                await db.execute(
                    text(f"DELETE FROM chunks WHERE id IN ({placeholders})"),
                    params
                )
            logger.info(f"MySQL delete success: {len(chunk_ids)} chunks")
        except Exception as e:
            logger.error(f"MySQL delete failed: {e}")
            return False

        # Step 3: Delete from Milvus (sync operation, run in thread)
        try:
            from app.rag.vector_store import vector_store
            await asyncio.to_thread(vector_store.delete_vectors, chunk_ids)
            logger.info(f"Milvus delete success: {len(chunk_ids)} vectors")
        except Exception as e:
            logger.error(f"Milvus delete failed (MySQL already deleted): {e}")
            # MySQL already deleted, log but don't fail
            # Next Milvus cleanup can handle orphaned vectors

        return True

    def get_status(self) -> dict[str, Any]:
        """Get current consistency status."""
        return {
            "mysql": self._mysql_ok,
            "milvus": self._milvus_ok,
            "consistent": self._mysql_ok == self._milvus_ok,
        }


# Global instance
consistency_manager = DataConsistencyManager()
