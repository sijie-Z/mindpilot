"""
Knowledge base management API.
"""
import asyncio
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from app.auth import TokenData, get_optional_user
from app.storage.database import get_db_session

router = APIRouter()


class KnowledgeCreate(BaseModel):
    name: str
    description: str | None = None


class KnowledgeUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class KnowledgeResponse(BaseModel):
    id: str
    name: str
    description: str | None
    doc_count: int
    chunk_count: int
    created_at: datetime


@router.post("/", response_model=KnowledgeResponse)
async def create_knowledge(
    data: KnowledgeCreate,
    current_user: TokenData | None = Depends(get_optional_user),
):
    """Create a new knowledge base."""
    kb_id = str(uuid.uuid4())

    async with get_db_session() as db:
        await db.execute(
            text("INSERT INTO knowledges (id, name, description) VALUES (:id, :name, :desc)"),
            {"id": kb_id, "name": data.name, "desc": data.description or ""}
        )

    return KnowledgeResponse(
        id=kb_id,
        name=data.name,
        description=data.description,
        doc_count=0,
        chunk_count=0,
        created_at=datetime.now(),
    )


@router.get("/")
async def list_knowledges():
    """List all knowledge bases."""
    async with get_db_session() as db:
        result = await db.execute(
            text("SELECT id, name, description, doc_count, chunk_count, created_at FROM knowledges")
        )
        kbs = result.fetchall()
        return {
            "knowledges": [
                {
                    "id": kb[0],
                    "name": kb[1],
                    "description": kb[2],
                    "doc_count": kb[3],
                    "chunk_count": kb[4],
                    "created_at": str(kb[5]),
                }
                for kb in kbs
            ]
        }


@router.get("/{kb_id}")
async def get_knowledge(kb_id: str):
    """Get knowledge base details."""
    async with get_db_session() as db:
        result = await db.execute(
            text("SELECT id, name, description, doc_count, chunk_count, created_at "
                 "FROM knowledges WHERE id=:kb_id"),
            {"kb_id": kb_id}
        )
        kb = result.fetchone()
        if not kb:
            raise HTTPException(404, "Knowledge base not found")

        return {
            "id": kb[0],
            "name": kb[1],
            "description": kb[2],
            "doc_count": kb[3],
            "chunk_count": kb[4],
            "created_at": str(kb[5]),
        }


@router.put("/{kb_id}")
async def update_knowledge(kb_id: str, data: KnowledgeUpdate):
    """Update knowledge base."""
    updates = []
    params = {"kb_id": kb_id}
    if data.name:
        updates.append("name=:name")
        params["name"] = data.name
    if data.description is not None:
        updates.append("description=:desc")
        params["desc"] = data.description

    if not updates:
        raise HTTPException(400, "No updates provided")

    async with get_db_session() as db:
        await db.execute(
            text(f"UPDATE knowledges SET {', '.join(updates)} WHERE id=:kb_id"),
            params
        )

    return {"status": "updated", "kb_id": kb_id}


@router.delete("/{kb_id}")
async def delete_knowledge(kb_id: str):
    """Delete knowledge base and all its documents."""
    async with get_db_session() as db:
        # Get all document IDs
        result = await db.execute(
            text("SELECT id FROM documents WHERE knowledge_id=:kb_id"),
            {"kb_id": kb_id}
        )
        doc_ids = [row[0] for row in result.fetchall()]

        # Delete chunks
        for doc_id in doc_ids:
            # Get chunk IDs for Milvus deletion
            chunk_result = await db.execute(
                text("SELECT id FROM chunks WHERE doc_id=:doc_id"),
                {"doc_id": doc_id}
            )
            chunk_ids = [row[0] for row in chunk_result.fetchall()]

            # Delete from Milvus (sync operation, run in thread)
            if chunk_ids:
                from app.rag.vector_store import vector_store
                await asyncio.to_thread(vector_store.delete_vectors, chunk_ids)

            # Delete chunks from MySQL
            await db.execute(
                text("DELETE FROM chunks WHERE doc_id=:doc_id"),
                {"doc_id": doc_id}
            )

        # Delete documents
        await db.execute(
            text("DELETE FROM documents WHERE knowledge_id=:kb_id"),
            {"kb_id": kb_id}
        )

        # Delete knowledge base
        await db.execute(
            text("DELETE FROM knowledges WHERE id=:kb_id"),
            {"kb_id": kb_id}
        )

    return {"status": "deleted", "kb_id": kb_id}


@router.get("/{kb_id}/documents")
async def list_knowledge_documents(kb_id: str):
    """List documents in a knowledge base."""
    async with get_db_session() as db:
        result = await db.execute(
            text("SELECT id, filename, file_type, status, chunks, created_at "
                 "FROM documents WHERE knowledge_id=:kb_id"),
            {"kb_id": kb_id}
        )
        docs = result.fetchall()

        return {
            "documents": [
                {
                    "id": doc[0],
                    "filename": doc[1],
                    "file_type": doc[2],
                    "status": doc[3],
                    "chunks": doc[4],
                    "created_at": str(doc[5]),
                }
                for doc in docs
            ]
        }


# === Retrieval Config & Stats ===

class RetrievalConfigUpdate(BaseModel):
    vector_weight: float | None = None
    bm25_weight: float | None = None
    top_k: int | None = None
    rerank_enabled: bool | None = None


@router.get("/retrieval-config/config")
async def get_retrieval_config(
    current_user: TokenData | None = Depends(get_optional_user),
):
    """Get current retrieval configuration."""
    async with get_db_session() as db:
        result = await db.execute(
            text("SELECT vector_weight, bm25_weight, top_k, rerank_enabled FROM retrieval_configs LIMIT 1")
        )
        config = result.fetchone()

        if not config:
            return {
                "vector_weight": 0.7,
                "bm25_weight": 0.3,
                "top_k": 10,
                "rerank_enabled": True,
            }

        return {
            "vector_weight": config[0],
            "bm25_weight": config[1],
            "top_k": config[2],
            "rerank_enabled": bool(config[3]),
        }


@router.put("/retrieval-config/config")
async def update_retrieval_config(
    config: RetrievalConfigUpdate,
    current_user: TokenData | None = Depends(get_optional_user),
):
    """Update retrieval configuration."""
    async with get_db_session() as db:
        # Check if config exists
        result = await db.execute(text("SELECT id FROM retrieval_configs LIMIT 1"))
        exists = result.fetchone()

        if exists:
            updates = []
            params = {"config_id": exists[0]}
            if config.vector_weight is not None:
                updates.append("vector_weight=:vw")
                params["vw"] = config.vector_weight
            if config.bm25_weight is not None:
                updates.append("bm25_weight=:bw")
                params["bw"] = config.bm25_weight
            if config.top_k is not None:
                updates.append("top_k=:top_k")
                params["top_k"] = config.top_k
            if config.rerank_enabled is not None:
                updates.append("rerank_enabled=:re")
                params["re"] = int(config.rerank_enabled)

            if updates:
                await db.execute(
                    text(f"UPDATE retrieval_configs SET {', '.join(updates)} WHERE id=:config_id"),
                    params
                )
        else:
            config_id = str(uuid.uuid4())
            await db.execute(
                text("INSERT INTO retrieval_configs (id, vector_weight, bm25_weight, top_k, rerank_enabled) "
                     "VALUES (:id, :vw, :bw, :top_k, :re)"),
                {"id": config_id, "vw": config.vector_weight or 0.7,
                 "bw": config.bm25_weight or 0.3, "top_k": config.top_k or 10,
                 "re": int(config.rerank_enabled if config.rerank_enabled is not None else True)}
            )

    return await get_retrieval_config()


@router.get("/stats/overview")
async def get_system_stats():
    """Get system statistics overview."""
    async with get_db_session() as db:
        # Total queries from messages
        result = await db.execute(
            text("SELECT COUNT(*) FROM messages WHERE role='user'")
        )
        total_queries = result.fetchone()[0]

        # Average score from evaluations
        result = await db.execute(
            text("SELECT AVG(answer_relevance) FROM evaluations")
        )
        avg_score = result.fetchone()[0] or 0.0

        # Active sessions
        result = await db.execute(
            text("SELECT COUNT(DISTINCT session_id) FROM messages "
                 "WHERE created_at > DATE_SUB(NOW(), INTERVAL 1 HOUR)")
        )
        active_sessions = result.fetchone()[0]

        return {
            "total_queries": total_queries,
            "avg_latency": 0,
            "token_usage": "0",
            "avg_score": round(float(avg_score), 1),
            "active_sessions": active_sessions,
        }


# === Knowledge Base Search ===

class KnowledgeSearchRequest(BaseModel):
    query: str
    knowledge_id: str | None = None
    top_k: int = 10
    vector_weight: float = 0.7


@router.post("/search")
async def search_knowledge(
    data: KnowledgeSearchRequest,
    current_user: TokenData | None = Depends(get_optional_user),
):
    """
    Search across knowledge bases.
    Uses hybrid retrieval (vector + BM25).
    """
    from app.rag.retriever import retriever

    try:
        # Set weights if provided
        if data.vector_weight != 0.7:
            retriever.set_weights(data.vector_weight, 1 - data.vector_weight)

        # Perform search
        results = await retriever.search(
            query=data.query,
            knowledge_id=data.knowledge_id or "",
            top_k=data.top_k,
        )

        return {
            "query": data.query,
            "results": results,
            "count": len(results),
        }

    except Exception as e:
        raise HTTPException(500, f"Search failed: {str(e)}")


@router.get("/{kb_id}/search")
async def search_in_knowledge(
    kb_id: str,
    q: str = "",
    limit: int = 20,
):
    """
    Search within a specific knowledge base.
    Simple BM25 search for chunks.
    """
    if not q:
        raise HTTPException(400, "Query parameter 'q' is required")

    async with get_db_session() as db:
        # Use fulltext search
        result = await db.execute(
            text("""
                SELECT id, chunk_index, content, metadata
                FROM chunks
                WHERE doc_id IN (SELECT id FROM documents WHERE knowledge_id = :kb_id)
                AND MATCH(content) AGAINST(:query IN NATURAL LANGUAGE MODE)
                LIMIT :limit
            """),
            {"kb_id": kb_id, "query": q, "limit": limit}
        )
        chunks = result.fetchall()

        # Fallback to LIKE if fulltext returns nothing
        if not chunks:
            result = await db.execute(
                text("""
                    SELECT id, chunk_index, content, metadata
                    FROM chunks
                    WHERE doc_id IN (SELECT id FROM documents WHERE knowledge_id = :kb_id)
                    AND content LIKE :pattern
                    LIMIT :limit
                """),
                {"kb_id": kb_id, "pattern": f"%{q}%", "limit": limit}
            )
            chunks = result.fetchall()

        return [
            {
                "id": c[0],
                "chunk_index": c[1],
                "content": c[2],
                "metadata": c[3] or {},
            }
            for c in chunks
        ]


@router.get("/{kb_id}/chunks")
async def list_knowledge_chunks(
    kb_id: str,
    skip: int = 0,
    limit: int = 50,
):
    """List chunks in a knowledge base."""
    async with get_db_session() as db:
        result = await db.execute(
            text("""
                SELECT c.id, c.chunk_index, c.content, c.metadata, d.filename
                FROM chunks c
                JOIN documents d ON c.doc_id = d.id
                WHERE d.knowledge_id = :kb_id
                ORDER BY d.created_at DESC, c.chunk_index ASC
                LIMIT :limit OFFSET :skip
            """),
            {"kb_id": kb_id, "limit": limit, "skip": skip}
        )
        chunks = result.fetchall()

        return [
            {
                "id": c[0],
                "chunk_index": c[1],
                "content": c[2],
                "metadata": c[3] or {},
                "filename": c[4],
            }
            for c in chunks
        ]
