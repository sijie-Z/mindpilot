"""
Text chunker with Chinese-optimized splitting strategy.
"""
from dataclasses import dataclass
from typing import Any


@dataclass
class Chunk:
    """Document chunk."""
    id: str
    content: str
    metadata: dict[str, Any]
    chunk_index: int


class TextChunker:
    """
    Split text into chunks with Chinese-optimized strategy.
    Uses semantic boundaries (paragraphs, sentences) instead of fixed size.
    """

    # Chinese sentence endings
    SENTENCE_SEPARATORS = [
        "\n\n",  # Paragraph break (highest priority)
        "\n",
        "。", "！", "？",  # Chinese sentence endings
        "；",  # Chinese semicolon
        ".", "!", "?",  # English sentence endings
        " ",
        "",
    ]

    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 100,
        min_chunk_size: int = 50,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size

    def chunk_text(
        self,
        text: str,
        metadata: dict[str, Any] = None,
    ) -> list[Chunk]:
        """
        Split text into chunks.

        Args:
            text: Input text
            metadata: Additional metadata to attach to each chunk

        Returns:
            List of Chunk objects
        """
        if not text or not text.strip():
            return []

        metadata = metadata or {}

        # Split into sentences first
        sentences = self._split_sentences(text)

        # Merge sentences into chunks
        chunks = self._merge_sentences(sentences, metadata)

        return chunks

    def chunk_pages(
        self,
        pages: list[dict[str, Any]],
        base_metadata: dict[str, Any] = None,
    ) -> list[Chunk]:
        """
        Chunk document pages.

        Args:
            pages: List of page dicts from parser
            base_metadata: Base metadata (filename, etc.)

        Returns:
            List of Chunk objects
        """
        all_chunks = []
        chunk_index = 0

        for page in pages:
            page_text = page.get("text", "")
            tables = page.get("tables", [])

            # Chunk main text
            if page_text.strip():
                page_metadata = {
                    **(base_metadata or {}),
                    "page": page.get("page", 0),
                    "type": "text",
                }
                text_chunks = self.chunk_text(page_text, page_metadata)

                for chunk in text_chunks:
                    chunk.chunk_index = chunk_index
                    chunk.id = f"chunk_{chunk_index}"
                    all_chunks.append(chunk)
                    chunk_index += 1

            # Add tables as separate chunks
            for i, table in enumerate(tables):
                all_chunks.append(Chunk(
                    id=f"chunk_{chunk_index}",
                    content=table,
                    metadata={
                        **(base_metadata or {}),
                        "page": page.get("page", 0),
                        "type": "table",
                        "table_index": i,
                    },
                    chunk_index=chunk_index,
                ))
                chunk_index += 1

        return all_chunks

    def _split_sentences(self, text: str) -> list[str]:
        """Split text into sentences using Chinese-aware separators."""
        sentences = []
        current = ""

        for char in text:
            current += char
            if char in self.SENTENCE_SEPARATORS[:7]:  # Up to Chinese sentence endings
                if current.strip():
                    sentences.append(current.strip())
                current = ""

        if current.strip():
            sentences.append(current.strip())

        return sentences

    def _merge_sentences(
        self,
        sentences: list[str],
        metadata: dict[str, Any],
    ) -> list[Chunk]:
        """Merge sentences into chunks respecting size limits."""
        chunks = []
        current_text = ""

        for sentence in sentences:
            # Check if adding this sentence exceeds chunk size
            if len(current_text) + len(sentence) > self.chunk_size and current_text:
                # Save current chunk
                chunks.append(self._create_chunk(
                    current_text,
                    len(chunks),
                    metadata,
                ))

                # Keep overlap from end of current chunk
                overlap_text = self._get_overlap(current_text)
                current_text = overlap_text + sentence
            else:
                current_text += sentence

        # Don't forget the last chunk
        if current_text.strip():
            # If last chunk is too small, merge with previous
            if len(current_text) < self.min_chunk_size and chunks:
                last_chunk = chunks[-1]
                last_chunk.content += current_text
            else:
                chunks.append(self._create_chunk(
                    current_text,
                    len(chunks),
                    metadata,
                ))

        return chunks

    def _get_overlap(self, text: str) -> str:
        """Get overlap text from end of chunk."""
        if len(text) <= self.chunk_overlap:
            return text

        # Find last sentence boundary within overlap range
        overlap_text = text[-self.chunk_overlap:]
        for sep in self.SENTENCE_SEPARATORS:
            idx = overlap_text.find(sep)
            if idx != -1:
                return overlap_text[idx + len(sep):]

        return overlap_text

    def _create_chunk(
        self,
        content: str,
        index: int,
        metadata: dict[str, Any],
    ) -> Chunk:
        """Create a Chunk object."""
        return Chunk(
            id=f"chunk_{index}",
            content=content.strip(),
            metadata=metadata,
            chunk_index=index,
        )
