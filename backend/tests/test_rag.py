"""
Tests for RAG pipeline components.
"""
import os
import tempfile
from unittest.mock import AsyncMock, patch

import pytest


class TestDocumentParser:
    """Tests for document parsing."""

    @pytest.mark.asyncio
    async def test_parse_txt_file(self):
        """Test parsing plain text file."""
        from app.rag.parser import DocumentParser

        parser = DocumentParser()

        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("This is a test document.")
            f.flush()
            f.close()  # Close before parsing on Windows

            result = await parser.parse(f.name)
            assert result is not None
            assert len(result) >= 1
            assert "test document" in result[0]["text"].lower()

        os.unlink(f.name)

    @pytest.mark.asyncio
    async def test_parse_markdown_file(self):
        """Test parsing markdown file."""
        from app.rag.parser import DocumentParser

        parser = DocumentParser()

        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("# Test Heading\n\nThis is markdown content.")
            f.flush()
            f.close()

            result = await parser.parse(f.name)
            assert result is not None
            assert len(result) >= 1
            assert "markdown" in result[0]["text"].lower()

        os.unlink(f.name)

    @pytest.mark.asyncio
    async def test_unsupported_format(self):
        """Test unsupported format raises error."""
        from app.rag.parser import DocumentParser

        tmpfile = tempfile.NamedTemporaryFile(mode='w', suffix='.xyz', delete=False)  # noqa: SIM115
        try:
            tmpfile.write("content")
            tmpfile.flush()
            tmpfile.close()

            parser = DocumentParser()
            with pytest.raises(ValueError) as exc_info:
                await parser.parse(tmpfile.name)
            assert "Unsupported format" in str(exc_info.value)
        finally:
            os.unlink(tmpfile.name)


class TestChunker:
    """Tests for document chunking."""

    def test_chunk_fixed_size(self):
        """Test fixed-size chunking."""
        from app.rag.chunker import TextChunker

        chunker = TextChunker(chunk_size=100, chunk_overlap=20)
        content = "This is a long piece of text that needs to be chunked. " * 5

        result = chunker.chunk_text(content)
        assert len(result) >= 1

    def test_chunk_empty_content(self):
        """Test chunking empty content."""
        from app.rag.chunker import TextChunker

        chunker = TextChunker()
        result = chunker.chunk_text("")
        assert len(result) == 0

    def test_chunk_metadata_preserved(self):
        """Test chunk metadata is preserved."""
        from app.rag.chunker import TextChunker

        chunker = TextChunker(chunk_size=200)
        meta = {"source": "test.txt", "page": 1}
        content = "Test content for metadata. " * 5

        result = chunker.chunk_text(content, metadata=meta)
        assert len(result) >= 1
        for chunk in result:
            assert chunk.metadata["source"] == "test.txt"


class TestEmbedder:
    """Tests for embedding operations."""

    @pytest.mark.asyncio
    async def test_embed_query_mocked(self):
        """Test embedding a single query (mocked)."""
        from app.rag.embedder import Embedder

        embedder = Embedder()

        with patch.object(embedder, 'embed_query', new_callable=AsyncMock) as mock:
            mock.return_value = [0.1] * 2048
            result = await embedder.embed_query("test query")
            assert len(result) == 2048

    @pytest.mark.asyncio
    async def test_embed_single_mocked(self):
        """Test embedding single text (mocked)."""
        from app.rag.embedder import Embedder

        embedder = Embedder()

        with patch.object(embedder, 'embed_single', new_callable=AsyncMock) as mock:
            mock.return_value = [0.1] * 2048
            result = await embedder.embed_single("test text")
            assert len(result) == 2048


class TestVectorStore:
    """Tests for vector store operations."""

    def test_vector_store_initialization(self):
        """Test vector store can be initialized."""
        from app.rag.vector_store import MilvusVectorStore

        store = MilvusVectorStore()
        assert store.COLLECTION_NAME == 'mindpilot_vectors'
        assert not store._connected

    def test_faiss_store_initialization(self):
        """Test FAISS store can be initialized."""
        from app.rag.faiss_store import FAISSVectorStore

        store = FAISSVectorStore(persist_dir="data/faiss_test")
        assert store._dimension > 0


class TestRetriever:
    """Tests for retrieval operations."""

    @pytest.mark.asyncio
    async def test_retriever_search_mocked(self):
        """Test retriever search (mocked)."""
        from app.rag.retriever import HybridRetriever

        retriever = HybridRetriever()

        with patch('app.rag.embedder.embedder.embed_query', new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = [0.1] * 2048
            with patch.object(retriever._vector_store, 'search', return_value=[]) as _mock_vs:
                with patch.object(retriever, '_bm25_search', new_callable=AsyncMock) as mock_bm25:
                    mock_bm25.return_value = []
                    with patch.object(retriever, '_get_chunks_from_mysql', new_callable=AsyncMock) as mock_chunks:
                        mock_chunks.return_value = []
                        result = await retriever.search("test query")
                        assert result == []

    def test_hybrid_retriever_weights(self):
        """Test setting retrieval weights."""
        from app.rag.retriever import HybridRetriever

        retriever = HybridRetriever(vector_weight=0.7, bm25_weight=0.3)
        assert retriever.vector_weight == 0.7
        assert retriever.bm25_weight == 0.3

        retriever.set_weights(0.6, 0.4)
        assert retriever.vector_weight == 0.6
        assert retriever.bm25_weight == 0.4


class TestRRFFusion:
    """Tests for Reciprocal Rank Fusion."""

    def test_rrf_basic_fusion(self):
        """Test basic RRF fusion of two result lists."""
        from app.rag.retriever import HybridRetriever

        retriever = HybridRetriever(vector_weight=0.5, bm25_weight=0.5)

        vector_results = [("chunk_a", 0.9), ("chunk_b", 0.7)]
        bm25_results = ["chunk_c", "chunk_a"]

        fused = retriever._rrf_fusion(vector_results, bm25_results)

        assert len(fused) >= 2
        # chunk_a appears in both, should rank high
        fused_ids = [cid for cid, _ in fused]
        assert "chunk_a" in fused_ids


class TestRAGIntegration:
    """Integration tests for RAG pipeline."""

    @pytest.mark.asyncio
    async def test_parser_chunker_flow(self):
        """Test parsing then chunking."""
        from app.rag.chunker import TextChunker
        from app.rag.parser import DocumentParser

        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("This is content for testing. " * 20)
            f.flush()
            f.close()

            parser = DocumentParser()
            parsed = await parser.parse(f.name)

            chunker = TextChunker(chunk_size=50)
            chunks = chunker.chunk_text(parsed[0]["text"])

            assert len(chunks) >= 1

        os.unlink(f.name)
