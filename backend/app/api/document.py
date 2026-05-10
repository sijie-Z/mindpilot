"""
Document upload and management API.
Uses MySQL + Milvus dual-write with rollback for data consistency.
"""
import os
import uuid

import aiofiles
from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import text

from app.config import settings
from app.core.audit import log_action
from app.core.logger import get_logger
from app.rag.chunker import TextChunker
from app.rag.consistency import consistency_manager
from app.rag.embedder import embedder
from app.rag.parser import DocumentParser
from app.storage.database import get_db_session

logger = get_logger(__name__)

router = APIRouter()

# Upload directory
UPLOAD_DIR = "data/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


class DocumentResponse(BaseModel):
    doc_id: str
    filename: str
    status: str
    chunks: int


parser = DocumentParser()
chunker = TextChunker(
    chunk_size=settings.CHUNK_SIZE,
    chunk_overlap=settings.CHUNK_OVERLAP,
)


async def _update_progress(doc_id: str, progress: int, detail: str):
    """Update document processing progress."""
    async with get_db_session() as db:
        await db.execute(
            text("UPDATE documents SET progress=:p, progress_detail=:d WHERE id=:doc_id"),
            {"p": progress, "d": detail, "doc_id": doc_id}
        )


async def process_document(doc_id: str, file_path: str, knowledge_id: str):
    """
    Background task to process uploaded document.
    Pipeline: Parse -> Chunk -> Embed -> Dual-write (MySQL + Milvus)
    Uses DataConsistencyManager for atomicity.
    """
    async with get_db_session() as db:
        try:
            # Update status to processing
            await db.execute(
                text("UPDATE documents SET status='processing', progress=0, progress_detail='准备中' WHERE id=:doc_id"),
                {"doc_id": doc_id}
            )

            # Step 1: Parse document
            await _update_progress(doc_id, 10, "正在解析文档...")
            pages = await parser.parse(file_path)

            # Handle OCR for scanned PDFs
            for page in pages:
                if page.get("needs_ocr"):
                    await _update_progress(doc_id, 20, "正在 OCR 识别...")
                    ocr_pages = await parser.parse_with_ocr(file_path)
                    pages = ocr_pages
                    break

            filename = os.path.basename(file_path)

            # Step 2: Chunk pages
            await _update_progress(doc_id, 35, "正在分块处理...")
            chunks = chunker.chunk_pages(
                pages,
                base_metadata={
                    "filename": filename,
                    "knowledge_id": knowledge_id,
                }
            )

            if not chunks:
                await db.execute(
                    text("UPDATE documents SET status='done', chunks=0, progress=100, progress_detail='完成' WHERE id=:doc_id"),
                    {"doc_id": doc_id}
                )
                return

            # Step 3: Generate embeddings
            await _update_progress(doc_id, 50, f"正在生成向量 ({len(chunks)} 个分块)...")
            texts = [c.content for c in chunks]
            embeddings = await embedder.embed_batch(texts)

            # Step 4: Build chunk data
            await _update_progress(doc_id, 75, "正在写入数据库...")
            chunk_data = [
                {
                    "id": c.id,
                    "chunk_index": c.chunk_index,
                    "content": c.content,
                    "metadata": c.metadata,
                }
                for c in chunks
            ]

            # Dual-write: MySQL + Milvus with rollback
            success = await consistency_manager.insert_chunks_with_rollback(
                chunks=chunk_data,
                embeddings=embeddings,
                knowledge_id=knowledge_id,
                doc_id=doc_id,
            )

            if not success:
                raise Exception("Failed to store chunks in vector store")

            # Step 5: Done
            await _update_progress(doc_id, 95, "正在更新索引...")
            await db.execute(
                text("UPDATE documents SET status='done', chunks=:chunks, progress=100, progress_detail='完成' WHERE id=:doc_id"),
                {"chunks": len(chunks), "doc_id": doc_id}
            )

            # Update knowledge base stats
            await db.execute(
                text("UPDATE knowledges SET chunk_count = chunk_count + :chunks, "
                     "doc_count = doc_count + 1 WHERE id=:knowledge_id"),
                {"chunks": len(chunks), "knowledge_id": knowledge_id}
            )

            logger.info(f"Document processed: {doc_id}, {len(chunks)} chunks")

        except Exception as e:
            logger.error(f"Document processing failed: {e}")
            await db.execute(
                text("UPDATE documents SET status='failed', error_message=:error, progress=0, progress_detail='失败' WHERE id=:doc_id"),
                {"error": str(e), "doc_id": doc_id}
            )


@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    knowledge_id: str | None = Form(None),
    knowledge_name: str | None = Form(None),
    replace_existing: bool = Form(True),
):
    """
    Upload a document and process it in the background.

    If replace_existing is True and a document with the same filename exists
    in the same knowledge base, the old document will be replaced.
    """
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in {".pdf", ".docx", ".doc", ".pptx", ".ppt", ".txt", ".md"}:
        raise HTTPException(400, f"Unsupported file type: {ext}")

    # Check file size
    content = await file.read()
    max_size = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(content) > max_size:
        raise HTTPException(413, f"File too large. Maximum size is {settings.MAX_UPLOAD_SIZE_MB}MB")

    # Create knowledge base if needed
    async with get_db_session() as db:
        if not knowledge_id and knowledge_name:
            knowledge_id = str(uuid.uuid4())
            await db.execute(
                text("INSERT INTO knowledges (id, name) VALUES (:kid, :name)"),
                {"kid": knowledge_id, "name": knowledge_name}
            )
        elif not knowledge_id:
            knowledge_id = "default"

        # Check for existing document with same filename in same knowledge base
        if replace_existing:
            existing = await db.execute(
                text("SELECT id FROM documents WHERE knowledge_id=:kid AND filename=:fname AND status != 'failed'"),
                {"kid": knowledge_id, "fname": file.filename}
            )
            existing_doc = existing.fetchone()

            if existing_doc:
                old_doc_id = existing_doc[0]
                logger.info(f"Replacing existing document: {old_doc_id} with new version")

                # Delete old document chunks from Milvus
                chunk_result = await db.execute(
                    text("SELECT id FROM chunks WHERE doc_id=:doc_id"),
                    {"doc_id": old_doc_id}
                )
                old_chunk_ids = [row[0] for row in chunk_result.fetchall()]

                if old_chunk_ids:
                    from app.rag.vector_store import vector_store
                    import asyncio
                    await asyncio.to_thread(vector_store.delete_vectors, old_chunk_ids)

                # Delete old chunks from MySQL
                await db.execute(
                    text("DELETE FROM chunks WHERE doc_id=:doc_id"),
                    {"doc_id": old_doc_id}
                )

                # Delete old document record
                await db.execute(
                    text("DELETE FROM documents WHERE id=:doc_id"),
                    {"doc_id": old_doc_id}
                )

                # Update knowledge base stats
                await db.execute(
                    text("UPDATE knowledges SET doc_count = doc_count - 1 WHERE id=:kid"),
                    {"kid": knowledge_id}
                )

        doc_id = str(uuid.uuid4())

        # Save file
        file_path = os.path.join(UPLOAD_DIR, f"{doc_id}{ext}")
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(content)

        # Create document record
        await db.execute(
            text("INSERT INTO documents (id, knowledge_id, filename, file_path, file_type, status) "
                 "VALUES (:id, :kid, :filename, :path, :ftype, 'pending')"),
            {"id": doc_id, "kid": knowledge_id, "filename": file.filename,
             "path": file_path, "ftype": ext[1:]}
        )

    # Process in background
    background_tasks.add_task(process_document, doc_id, file_path, knowledge_id)

    await log_action(
        action="document_upload",
        resource_type="document",
        resource_id=doc_id,
        detail=f"filename={file.filename}, knowledge_id={knowledge_id}",
    )

    return DocumentResponse(
        doc_id=doc_id,
        filename=file.filename,
        status="processing",
        chunks=0,
    )


@router.get("/list")
async def list_documents(
    knowledge_id: str | None = None,
    tag: str | None = None,
    file_type: str | None = None,
):
    """List all active documents (excluding soft-deleted), with optional filters."""
    async with get_db_session() as db:
        conditions = ["deleted_at IS NULL"]
        params = {}
        if knowledge_id:
            conditions.append("knowledge_id = :kid")
            params["kid"] = knowledge_id
        if tag:
            conditions.append("JSON_CONTAINS(tags, :tag)")
            params["tag"] = f'"{tag}"'
        if file_type:
            conditions.append("file_type = :ft")
            params["ft"] = file_type

        where = " AND ".join(conditions)
        result = await db.execute(
            text(f"SELECT id, knowledge_id, filename, file_type, status, chunks, progress, progress_detail, tags "
                 f"FROM documents WHERE {where}"),
            params
        )
        docs = result.fetchall()
        return {
            "documents": [
                {
                    "id": d[0],
                    "knowledge_id": d[1],
                    "filename": d[2],
                    "file_type": d[3],
                    "status": d[4],
                    "chunks": d[5],
                    "progress": d[6] or 0,
                    "progress_detail": d[7] or "",
                    "tags": d[8] or [],
                }
                for d in docs
            ]
        }


@router.delete("/{doc_id}")
async def delete_document(doc_id: str):
    """Soft-delete a document (move to recycle bin)."""
    from datetime import UTC, datetime
    async with get_db_session() as db:
        result = await db.execute(
            text("SELECT id, deleted_at FROM documents WHERE id=:doc_id"),
            {"doc_id": doc_id}
        )
        doc = result.fetchone()
        if not doc:
            raise HTTPException(404, "Document not found")
        if doc[1]:  # already deleted
            raise HTTPException(400, "Document already in recycle bin")

        await db.execute(
            text("UPDATE documents SET deleted_at = :now WHERE id=:doc_id"),
            {"doc_id": doc_id, "now": datetime.now(UTC)}
        )

    await log_action(action="document_delete", resource_type="document", resource_id=doc_id)
    return {"status": "deleted", "doc_id": doc_id}


@router.get("/recycle-bin")
async def list_deleted_documents(knowledge_id: str | None = None):
    """List documents in the recycle bin."""
    async with get_db_session() as db:
        if knowledge_id:
            result = await db.execute(
                text("SELECT id, knowledge_id, filename, file_type, chunks, deleted_at "
                     "FROM documents WHERE deleted_at IS NOT NULL AND knowledge_id=:kid "
                     "ORDER BY deleted_at DESC"),
                {"kid": knowledge_id}
            )
        else:
            result = await db.execute(
                text("SELECT id, knowledge_id, filename, file_type, chunks, deleted_at "
                     "FROM documents WHERE deleted_at IS NOT NULL "
                     "ORDER BY deleted_at DESC")
            )
        docs = result.fetchall()
        return {
            "documents": [
                {
                    "id": d[0],
                    "knowledge_id": d[1],
                    "filename": d[2],
                    "file_type": d[3],
                    "chunks": d[4],
                    "deleted_at": str(d[5]),
                }
                for d in docs
            ]
        }


@router.post("/{doc_id}/restore")
async def restore_document(doc_id: str):
    """Restore a document from the recycle bin."""
    async with get_db_session() as db:
        result = await db.execute(
            text("SELECT id, deleted_at FROM documents WHERE id=:doc_id"),
            {"doc_id": doc_id}
        )
        doc = result.fetchone()
        if not doc:
            raise HTTPException(404, "Document not found")
        if not doc[1]:
            raise HTTPException(400, "Document is not in recycle bin")

        await db.execute(
            text("UPDATE documents SET deleted_at = NULL WHERE id=:doc_id"),
            {"doc_id": doc_id}
        )

    return {"status": "restored", "doc_id": doc_id}


@router.delete("/{doc_id}/permanent")
async def permanent_delete_document(doc_id: str):
    """Permanently delete a document from the recycle bin (MySQL + Milvus)."""
    async with get_db_session() as db:
        result = await db.execute(
            text("SELECT id, deleted_at FROM documents WHERE id=:doc_id"),
            {"doc_id": doc_id}
        )
        doc = result.fetchone()
        if not doc:
            raise HTTPException(404, "Document not found")

    # Hard delete with consistency manager
    success = await consistency_manager.delete_document_with_rollback(doc_id)

    async with get_db_session() as db:
        await db.execute(
            text("DELETE FROM documents WHERE id=:doc_id"),
            {"doc_id": doc_id}
        )

    if not success:
        raise HTTPException(500, "Failed to delete document completely")

    await log_action(action="document_permanent_delete", resource_type="document", resource_id=doc_id)
    return {"status": "permanently_deleted", "doc_id": doc_id}


class BatchRequest(BaseModel):
    doc_ids: list[str]


class BatchMoveRequest(BaseModel):
    doc_ids: list[str]
    target_knowledge_id: str


class TagsUpdateRequest(BaseModel):
    tags: list[str]


@router.post("/batch-delete")
async def batch_delete_documents(req: BatchRequest):
    """Soft-delete multiple documents at once."""
    from datetime import UTC, datetime
    async with get_db_session() as db:
        now = datetime.now(UTC)
        for doc_id in req.doc_ids:
            result = await db.execute(
                text("SELECT id, deleted_at FROM documents WHERE id=:doc_id"),
                {"doc_id": doc_id}
            )
            doc = result.fetchone()
            if doc and not doc[1]:
                await db.execute(
                    text("UPDATE documents SET deleted_at = :now WHERE id=:doc_id"),
                    {"doc_id": doc_id, "now": now}
                )
    return {"status": "deleted", "count": len(req.doc_ids)}


@router.post("/batch-move")
async def batch_move_documents(req: BatchMoveRequest):
    """Move multiple documents to another knowledge base."""
    async with get_db_session() as db:
        # Verify target knowledge base exists
        target = await db.execute(
            text("SELECT id FROM knowledges WHERE id=:kid"),
            {"kid": req.target_knowledge_id}
        )
        if not target.fetchone():
            raise HTTPException(404, "Target knowledge base not found")

        for doc_id in req.doc_ids:
            result = await db.execute(
                text("SELECT id, knowledge_id, chunks FROM documents WHERE id=:doc_id AND deleted_at IS NULL"),
                {"doc_id": doc_id}
            )
            doc = result.fetchone()
            if not doc:
                continue

            old_kid = doc[1]
            chunk_count = doc[2] or 0

            # Update document's knowledge_id
            await db.execute(
                text("UPDATE documents SET knowledge_id=:new_kid WHERE id=:doc_id"),
                {"new_kid": req.target_knowledge_id, "doc_id": doc_id}
            )

            # Update chunk metadata
            await db.execute(
                text("UPDATE chunks SET chunk_metadata = JSON_SET(COALESCE(chunk_metadata, '{}'), '$.knowledge_id', :new_kid) WHERE doc_id=:doc_id"),
                {"new_kid": req.target_knowledge_id, "doc_id": doc_id}
            )

            # Update old knowledge base stats
            await db.execute(
                text("UPDATE knowledges SET doc_count = GREATEST(doc_count - 1, 0), chunk_count = GREATEST(chunk_count - :chunks, 0) WHERE id=:old_kid"),
                {"old_kid": old_kid, "chunks": chunk_count}
            )

            # Update new knowledge base stats
            await db.execute(
                text("UPDATE knowledges SET doc_count = doc_count + 1, chunk_count = chunk_count + :chunks WHERE id=:new_kid"),
                {"new_kid": req.target_knowledge_id, "chunks": chunk_count}
            )

    return {"status": "moved", "count": len(req.doc_ids)}


@router.put("/{doc_id}/tags")
async def update_document_tags(doc_id: str, req: TagsUpdateRequest):
    """Update tags for a document."""
    import json
    async with get_db_session() as db:
        result = await db.execute(
            text("SELECT id FROM documents WHERE id=:doc_id AND deleted_at IS NULL"),
            {"doc_id": doc_id}
        )
        if not result.fetchone():
            raise HTTPException(404, "Document not found")

        await db.execute(
            text("UPDATE documents SET tags=:tags WHERE id=:doc_id"),
            {"tags": json.dumps(req.tags), "doc_id": doc_id}
        )
    return {"status": "updated", "doc_id": doc_id, "tags": req.tags}


@router.get("/{doc_id}/status")
async def get_document_status(doc_id: str):
    """Get document processing status with progress."""
    async with get_db_session() as db:
        result = await db.execute(
            text("SELECT id, filename, status, chunks, error_message, progress, progress_detail FROM documents WHERE id=:doc_id"),
            {"doc_id": doc_id}
        )
        doc = result.fetchone()
        if not doc:
            raise HTTPException(404, "Document not found")
        return {
            "id": doc[0],
            "filename": doc[1],
            "status": doc[2],
            "chunks": doc[3],
            "error_message": doc[4],
            "progress": doc[5] or 0,
            "progress_detail": doc[6] or "",
        }
