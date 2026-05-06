"""
Document upload and management API.
Uses MySQL + Milvus dual-write with rollback for data consistency.
"""
import logging
import os
import uuid

import aiofiles
from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import text

from app.config import settings
from app.rag.chunker import TextChunker
from app.rag.consistency import consistency_manager
from app.rag.embedder import embedder
from app.rag.parser import DocumentParser
from app.storage.database import get_db_session

logger = logging.getLogger(__name__)

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
                text("UPDATE documents SET status='processing' WHERE id=:doc_id"),
                {"doc_id": doc_id}
            )

            # Parse document
            pages = await parser.parse(file_path)

            # Handle OCR for scanned PDFs
            for page in pages:
                if page.get("needs_ocr"):
                    ocr_pages = await parser.parse_with_ocr(file_path)
                    pages = ocr_pages
                    break

            filename = os.path.basename(file_path)

            # Chunk pages
            chunks = chunker.chunk_pages(
                pages,
                base_metadata={
                    "filename": filename,
                    "knowledge_id": knowledge_id,
                }
            )

            if not chunks:
                await db.execute(
                    text("UPDATE documents SET status='done', chunks=0 WHERE id=:doc_id"),
                    {"doc_id": doc_id}
                )
                return

            # Generate embeddings via Zhipu API
            texts = [c.content for c in chunks]
            embeddings = await embedder.embed_batch(texts)

            # Build chunk data for consistency manager
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

            # Update document status
            await db.execute(
                text("UPDATE documents SET status='done', chunks=:chunks WHERE id=:doc_id"),
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
                text("UPDATE documents SET status='failed', error_message=:error WHERE id=:doc_id"),
                {"error": str(e), "doc_id": doc_id}
            )


@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    knowledge_id: str | None = Form(None),
    knowledge_name: str | None = Form(None),
):
    """Upload a document and process it in the background."""
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in {".pdf", ".docx", ".doc", ".pptx", ".ppt", ".txt", ".md"}:
        raise HTTPException(400, f"Unsupported file type: {ext}")

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

        doc_id = str(uuid.uuid4())

        # Save file
        file_path = os.path.join(UPLOAD_DIR, f"{doc_id}{ext}")
        async with aiofiles.open(file_path, "wb") as f:
            content = await file.read()
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

    return DocumentResponse(
        doc_id=doc_id,
        filename=file.filename,
        status="processing",
        chunks=0,
    )


@router.get("/list")
async def list_documents(knowledge_id: str | None = None):
    """List all documents."""
    async with get_db_session() as db:
        if knowledge_id:
            result = await db.execute(
                text("SELECT id, knowledge_id, filename, file_type, status, chunks "
                     "FROM documents WHERE knowledge_id=:kid"),
                {"kid": knowledge_id}
            )
        else:
            result = await db.execute(
                text("SELECT id, knowledge_id, filename, file_type, status, chunks FROM documents")
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
                }
                for d in docs
            ]
        }


@router.delete("/{doc_id}")
async def delete_document(doc_id: str):
    """Delete a document with double-delete strategy (MySQL + Milvus)."""
    success = await consistency_manager.delete_document_with_rollback(doc_id)

    async with get_db_session() as db:
        await db.execute(
            text("DELETE FROM documents WHERE id=:doc_id"),
            {"doc_id": doc_id}
        )

    if not success:
        raise HTTPException(500, "Failed to delete document completely")

    return {"status": "deleted", "doc_id": doc_id}


@router.get("/{doc_id}/status")
async def get_document_status(doc_id: str):
    """Get document processing status."""
    async with get_db_session() as db:
        result = await db.execute(
            text("SELECT id, filename, status, chunks, error_message FROM documents WHERE id=:doc_id"),
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
        }
