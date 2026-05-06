"""
Embedding module using Zhipu API via async LLM client.
"""

from app.core.llm_client import AsyncLLMClient
from app.core.logger import get_logger

logger = get_logger(__name__)


class Embedder:
    """Async embedder using ZhipuAI Embedding API."""

    def __init__(self, llm: AsyncLLMClient | None = None):
        self.llm = llm or AsyncLLMClient()
        self.dimension = 2048

    async def embed_single(self, text: str) -> list[float]:
        """Embed a single text."""
        return await self.llm.embed_single(text)

    async def embed_query(self, query: str) -> list[float]:
        """Embed a query."""
        return await self.llm.embed_single(query)

    async def embed_batch(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        """Embed multiple texts in batches."""
        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            try:
                batch_embeddings = await self.llm.embed(batch)
                all_embeddings.extend(batch_embeddings)
            except Exception as e:
                logger.error("Embedding batch failed", batch_start=i, error=str(e))
                all_embeddings.extend([[0.0] * self.dimension] * len(batch))
        return all_embeddings


# Global embedder instance
embedder = Embedder()
