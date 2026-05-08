"""
Dependency injection container for MindPilot.

Replaces module-level global singletons with a single App container.
Each component receives its dependencies via constructor injection.
"""
import threading

from app.config import settings
from app.core.llm_client import AsyncLLMClient


class AppContainer:
    """
    Central dependency injection container.

    Usage:
        container = AppContainer()
        await container.init()

        # In API handlers:
        answer = await container.answer_agent.generate(query, docs)

        # In tests:
        container = AppContainer(llm=mock_llm, vector_store=mock_vs)
    """

    def __init__(
        self,
        llm: AsyncLLMClient | None = None,
        config=None,
    ):
        self.config = config or settings
        self._llm = llm
        self._lock = threading.Lock()

        # Lazily initialized components
        self._embedder = None
        self._reranker = None
        self._retriever = None
        self._vector_store = None
        self._faiss_store = None
        self._consistency_manager = None
        self._session_repo = None
        self._vision_processor = None
        self._ocr_processor = None
        self._skill_registry = None
        self._agent_graph = None

    @property
    def llm(self) -> AsyncLLMClient:
        if self._llm is None:
            self._llm = AsyncLLMClient()
        return self._llm

    @property
    def embedder(self):
        if self._embedder is None:
            from app.rag.embedder import Embedder
            self._embedder = Embedder(llm=self.llm)
        return self._embedder

    @property
    def reranker(self):
        if self._reranker is None:
            from app.rag.reranker import Reranker
            self._reranker = Reranker()
        return self._reranker

    @property
    def vector_store(self):
        """Get the configured vector store (Milvus or FAISS)."""
        if self._vector_store is None:
            if settings.VECTOR_STORE == "milvus":
                from app.rag.vector_store import vector_store
                self._vector_store = vector_store
            else:
                self._vector_store = self.faiss_store
        return self._vector_store

    @property
    def faiss_store(self):
        if self._faiss_store is None:
            from app.rag.faiss_store import FAISSVectorStore
            self._faiss_store = FAISSVectorStore()
        return self._faiss_store

    @property
    def retriever(self):
        if self._retriever is None:
            from app.rag.retriever import HybridRetriever
            self._retriever = HybridRetriever(
                vector_weight=settings.DEFAULT_VECTOR_WEIGHT,
                bm25_weight=settings.DEFAULT_BM25_WEIGHT,
            )
        return self._retriever

    @property
    def consistency_manager(self):
        if self._consistency_manager is None:
            from app.rag.consistency import DataConsistencyManager
            self._consistency_manager = DataConsistencyManager()
        return self._consistency_manager

    @property
    def session_repo(self):
        if self._session_repo is None:
            from app.storage.session_repo import SessionRepository
            self._session_repo = SessionRepository()
        return self._session_repo

    @property
    def vision_processor(self):
        if self._vision_processor is None:
            from app.multimodal.vision import VisionProcessor
            self._vision_processor = VisionProcessor(llm=self.llm)
        return self._vision_processor

    @property
    def ocr_processor(self):
        if self._ocr_processor is None:
            from app.multimodal.ocr import OCRProcessor
            self._ocr_processor = OCRProcessor()
        return self._ocr_processor

    @property
    def skill_registry(self):
        if self._skill_registry is None:
            from app.skills.registry import registry
            self._skill_registry = registry
        return self._skill_registry

    @property
    def agent_graph(self):
        if self._agent_graph is None:
            from app.agents.graph import create_agent_graph
            self._agent_graph = create_agent_graph()
        return self._agent_graph

    async def get_vector_store(self):
        """Async getter for vector store (handles lazy Milvus connection)."""
        vs = self.vector_store
        if not getattr(vs, '_connected', True):
            vs.connect()
        return vs

    def reset(self):
        """Reset all cached components (useful for testing)."""
        self._embedder = None
        self._reranker = None
        self._retriever = None
        self._vector_store = None
        self._faiss_store = None
        self._consistency_manager = None
        self._session_repo = None
        self._vision_processor = None
        self._ocr_processor = None
        self._skill_registry = None
        self._agent_graph = None


# Application-wide container instance
# This replaces the scattered module-level globals throughout the codebase.
# Tests can create their own container with mocks.
container = AppContainer()
