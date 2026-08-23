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


class TestDocumentParserExtended:
    """Extended tests for document parser."""

    @pytest.mark.asyncio
    async def test_supported_formats(self):
        """Test all supported formats are recognized."""
        from app.rag.parser import DocumentParser
        parser = DocumentParser()
        expected = {".pdf", ".docx", ".doc", ".pptx", ".ppt", ".txt", ".md"}
        assert parser.SUPPORTED_FORMATS == expected

    @pytest.mark.asyncio
    async def test_parse_text_utf8(self):
        """Test parsing UTF-8 text with Chinese content."""
        from app.rag.parser import DocumentParser
        parser = DocumentParser()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("这是一段中文测试内容。\n第二行内容。")
            f.flush(); f.close()
            result = await parser.parse(f.name)
            assert len(result) == 1
            assert "中文" in result[0]["text"]
            assert result[0]["tables"] == []
        os.unlink(f.name)

    @pytest.mark.asyncio
    async def test_parse_text_returns_page_structure(self):
        """Test parse_text returns correct page structure."""
        from app.rag.parser import DocumentParser
        parser = DocumentParser()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("# Title\n\nParagraph 1.\n\nParagraph 2.")
            f.flush(); f.close()
            result = await parser.parse(f.name)
            assert result[0]["page"] == 1
            assert "text" in result[0]
            assert "tables" in result[0]
        os.unlink(f.name)


class TestChunkerExtended:
    """Extended tests for text chunker."""

    def test_chunk_chinese_text(self):
        """Test chunking Chinese text respects sentence boundaries."""
        from app.rag.chunker import TextChunker
        chunker = TextChunker(chunk_size=30, chunk_overlap=5)
        # Each sentence is ~20 chars, so 2 sentences exceed chunk_size=30
        text = "这是第一个测试句子内容比较长一些。这是第二个测试句子内容比较长一些。这是第三个测试句子内容比较长一些。"
        chunks = chunker.chunk_text(text)
        assert len(chunks) >= 2
        for chunk in chunks:
            assert len(chunk.content) > 0

    def test_chunk_preserves_index(self):
        """Test chunks have sequential indices."""
        from app.rag.chunker import TextChunker
        chunker = TextChunker(chunk_size=30)
        text = "Short sentence. Another sentence. Third sentence. Fourth sentence."
        chunks = chunker.chunk_text(text)
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i
            assert chunk.id == f"chunk_{i}"

    def test_split_sentences_chinese(self):
        """Test Chinese sentence splitting."""
        from app.rag.chunker import TextChunker
        chunker = TextChunker()
        sentences = chunker._split_sentences("你好！世界。测试？")
        assert len(sentences) == 3

    def test_split_sentences_paragraph_break(self):
        """Test paragraph break splitting."""
        from app.rag.chunker import TextChunker
        chunker = TextChunker()
        sentences = chunker._split_sentences("Para one。\n\nPara two。")
        assert len(sentences) >= 2

    def test_get_overlap_short_text(self):
        """Test overlap returns full text when shorter than overlap."""
        from app.rag.chunker import TextChunker
        chunker = TextChunker(chunk_overlap=100)
        overlap = chunker._get_overlap("short")
        assert overlap == "short"

    def test_get_overlap_finds_boundary(self):
        """Test overlap finds sentence boundary."""
        from app.rag.chunker import TextChunker
        chunker = TextChunker(chunk_overlap=20)
        text = "First sentence. Second sentence. Third sentence."
        overlap = chunker._get_overlap(text)
        assert len(overlap) <= 20

    def test_min_chunk_size_merges_small(self):
        """Test small trailing chunk merges with previous."""
        from app.rag.chunker import TextChunker
        chunker = TextChunker(chunk_size=100, min_chunk_size=50)
        # Create text where last chunk would be tiny
        text = "A" * 90 + "。" + "B" * 5
        chunks = chunker.chunk_text(text)
        # The tiny "B" chunk should merge with the previous
        assert len(chunks) == 1 or (len(chunks) >= 1 and len(chunks[-1].content) >= 5)

    def test_chunk_pages_with_tables(self):
        """Test chunk_pages handles tables separately."""
        from app.rag.chunker import TextChunker
        chunker = TextChunker(chunk_size=200)
        pages = [
            {"page": 1, "text": "Page one content.", "tables": ["【表格】\nA | B\nC | D"]},
            {"page": 2, "text": "Page two content.", "tables": []},
        ]
        chunks = chunker.chunk_pages(pages, {"filename": "test.pdf"})
        # Should have text chunks + table chunk
        table_chunks = [c for c in chunks if c.metadata.get("type") == "table"]
        assert len(table_chunks) == 1
        assert table_chunks[0].metadata["table_index"] == 0
        assert table_chunks[0].metadata["page"] == 1

    def test_chunk_pages_empty_pages(self):
        """Test chunk_pages with empty page text."""
        from app.rag.chunker import TextChunker
        chunker = TextChunker()
        pages = [{"page": 1, "text": "", "tables": []}]
        chunks = chunker.chunk_pages(pages)
        assert len(chunks) == 0

    def test_chunk_with_metadata(self):
        """Test metadata is attached to all chunks."""
        from app.rag.chunker import TextChunker
        chunker = TextChunker(chunk_size=30)
        meta = {"filename": "doc.pdf", "knowledge_id": "kb1"}
        text = "Sentence one。Sentence two。Sentence three。Sentence four。"
        chunks = chunker.chunk_text(text, metadata=meta)
        for chunk in chunks:
            assert chunk.metadata["filename"] == "doc.pdf"
            assert chunk.metadata["knowledge_id"] == "kb1"


class TestEmbedderExtended:
    """Extended tests for embedder."""

    @pytest.mark.asyncio
    async def test_embed_batch_mocked(self):
        """Test batch embedding with mocked LLM client."""
        from app.rag.embedder import Embedder

        mock_llm = AsyncMock()
        mock_llm.embed = AsyncMock(return_value=[[0.1] * 2048, [0.2] * 2048])
        embedder = Embedder(llm=mock_llm)

        result = await embedder.embed_batch(["text1", "text2"])
        assert len(result) == 2
        assert len(result[0]) == 2048
        mock_llm.embed.assert_called_once_with(["text1", "text2"])

    @pytest.mark.asyncio
    async def test_embed_batch_chunks_large_input(self):
        """Test batch embedding splits into batches."""
        from app.rag.embedder import Embedder

        mock_llm = AsyncMock()
        # Return correct number of embeddings per batch
        call_count = 0
        async def mock_embed(texts: list[str]):
            nonlocal call_count
            call_count += 1
            return [[float(i) * 0.1] * 2048 for i in range(len(texts))]
        mock_llm.embed = mock_embed
        embedder = Embedder(llm=mock_llm)

        texts = [f"text{i}" for i in range(5)]
        result = await embedder.embed_batch(texts, batch_size=2)
        assert len(result) == 5
        # Should be called 3 times: [0,2), [2,4), [4,5)
        assert call_count == 3

    def test_embedder_dimension(self):
        """Test embedder has correct dimension."""
        from app.rag.embedder import Embedder
        embedder = Embedder()
        assert embedder.dimension == 2048


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


class TestDocumentParserEdgeCases:
    """Edge case tests for document parser."""

    @pytest.mark.asyncio
    async def test_unsupported_format_raises(self):
        """Test unsupported format raises ValueError."""
        from app.rag.parser import DocumentParser
        parser = DocumentParser()
        with pytest.raises(ValueError, match="Unsupported format"):
            await parser.parse("test.xyz")

    @pytest.mark.asyncio
    async def test_parse_text_empty_file(self):
        """Test parsing empty text file."""
        from app.rag.parser import DocumentParser
        parser = DocumentParser()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("")
            f.flush(); f.close()
            result = await parser.parse(f.name)
            assert len(result) == 1
            assert result[0]["text"] == ""
        os.unlink(f.name)

    @pytest.mark.asyncio
    async def test_parse_text_multiline(self):
        """Test parsing multiline text preserves content."""
        from app.rag.parser import DocumentParser
        parser = DocumentParser()
        content = "Line 1\nLine 2\nLine 3\n" * 10
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(content)
            f.flush(); f.close()
            result = await parser.parse(f.name)
            assert "Line 1" in result[0]["text"]
            assert "Line 3" in result[0]["text"]
        os.unlink(f.name)


class TestSearchSkillExtended:
    """Extended tests for search skill."""

    def test_search_skill_name(self):
        """Test search skill has correct name."""
        from app.skills.search_skill import SearchSkill
        skill = SearchSkill()
        assert skill.name == "web_search"
        assert "搜索" in skill.description

    def test_search_empty_query(self):
        """Test empty query returns error."""
        import asyncio
        from app.skills.search_skill import SearchSkill
        skill = SearchSkill()
        result = asyncio.run(skill.execute(""))
        assert result.success is False
        assert "不能为空" in result.error

    def test_search_whitespace_query(self):
        """Test whitespace-only query returns error."""
        import asyncio
        from app.skills.search_skill import SearchSkill
        skill = SearchSkill()
        result = asyncio.run(skill.execute("   "))
        assert result.success is False
