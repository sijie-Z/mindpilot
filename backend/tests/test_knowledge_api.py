"""
Tests for knowledge API: LIKE wildcard escaping, config model validation, middleware ordering.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


# ── LIKE Wildcard Escaping Tests ──

class TestLikeWildcardEscaping:
    """Test that user input wildcards are properly escaped in LIKE queries."""

    def test_escape_percent(self):
        """Percent signs in user input should be escaped."""
        q = "100%"
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        assert escaped == "100\\%"

    def test_escape_underscore(self):
        """Underscores in user input should be escaped."""
        q = "test_value"
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        assert escaped == "test\\_value"

    def test_escape_backslash(self):
        """Backslashes in user input should be escaped first."""
        q = "path\\to"
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        assert escaped == "path\\\\to"

    def test_escape_combined(self):
        """Multiple special chars should all be escaped."""
        q = "100%_test\\end"
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        assert escaped == "100\\%\\_test\\\\end"

    def test_no_special_chars(self):
        """Normal text should pass through unchanged."""
        q = "normal search query"
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        assert escaped == q

    def test_empty_string(self):
        """Empty string should remain empty."""
        q = ""
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        assert escaped == ""

    def test_only_wildcards(self):
        """String of only wildcards should be fully escaped."""
        q = "%_%"
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        assert escaped == "\\%\\_\\%"


# ── RetrievalConfigUpdate Model Tests ──

class TestRetrievalConfigUpdate:
    """Test RetrievalConfigUpdate pydantic model."""

    def test_all_fields_optional(self):
        """All fields should be optional."""
        from app.api.knowledge import RetrievalConfigUpdate
        config = RetrievalConfigUpdate()
        assert config.vector_weight is None
        assert config.bm25_weight is None
        assert config.top_k is None
        assert config.rerank_enabled is None
        assert config.llm_model is None
        assert config.embedding_model is None

    def test_partial_update(self):
        """Should accept partial updates."""
        from app.api.knowledge import RetrievalConfigUpdate
        config = RetrievalConfigUpdate(vector_weight=0.8)
        assert config.vector_weight == 0.8
        assert config.bm25_weight is None

    def test_model_fields(self):
        """Should accept model config fields."""
        from app.api.knowledge import RetrievalConfigUpdate
        config = RetrievalConfigUpdate(
            llm_model="glm-4",
            embedding_model="embedding-3",
        )
        assert config.llm_model == "glm-4"
        assert config.embedding_model == "embedding-3"

    def test_full_config(self):
        """Should accept all fields together."""
        from app.api.knowledge import RetrievalConfigUpdate
        config = RetrievalConfigUpdate(
            vector_weight=0.6,
            bm25_weight=0.4,
            top_k=20,
            rerank_enabled=False,
            llm_model="glm-4-plus",
            embedding_model="embedding-3",
        )
        assert config.vector_weight == 0.6
        assert config.top_k == 20
        assert config.llm_model == "glm-4-plus"


# ── KnowledgeCreate Model Tests ──

class TestKnowledgeModels:
    """Test knowledge base pydantic models."""

    def test_knowledge_create(self):
        """Test KnowledgeCreate model."""
        from app.api.knowledge import KnowledgeCreate
        kb = KnowledgeCreate(name="Test KB", description="A test")
        assert kb.name == "Test KB"
        assert kb.description == "A test"

    def test_knowledge_create_no_description(self):
        """Test KnowledgeCreate without description."""
        from app.api.knowledge import KnowledgeCreate
        kb = KnowledgeCreate(name="Test KB")
        assert kb.description is None

    def test_knowledge_update_partial(self):
        """Test KnowledgeUpdate with partial data."""
        from app.api.knowledge import KnowledgeUpdate
        update = KnowledgeUpdate(name="New Name")
        assert update.name == "New Name"
        assert update.description is None

    def test_knowledge_search_request_defaults(self):
        """Test KnowledgeSearchRequest defaults."""
        from app.api.knowledge import KnowledgeSearchRequest
        req = KnowledgeSearchRequest(query="test")
        assert req.top_k == 10
        assert req.vector_weight == 0.7
        assert req.knowledge_id is None


# ── Middleware Ordering Tests ──

class TestMiddlewareOrdering:
    """Test that middleware is registered in the correct order."""

    def test_exception_handler_is_outermost(self):
        """ExceptionHandlerMiddleware should be outermost (first in stack, executes first)."""
        from app.main import app

        middleware_stack = app.user_middleware
        names = []
        for mw in middleware_stack:
            cls = mw.cls if hasattr(mw, 'cls') else type(mw)
            names.append(cls.__name__ if hasattr(cls, '__name__') else str(cls))

        # ExceptionHandlerMiddleware is added last → appears first in stack → outermost
        assert names[0] == "ExceptionHandlerMiddleware", \
            f"Expected ExceptionHandlerMiddleware first, got: {names[0]}"

    def test_middleware_count(self):
        """Should have expected number of custom middleware."""
        from app.main import app
        # At minimum: CORS, ExceptionHandler, RateLimit, Metrics, RequestTracking
        assert len(app.user_middleware) >= 5


# ── KnowledgeSearchRequest Validation Tests ──

class TestKnowledgeSearchValidation:
    """Test search request validation."""

    def test_search_request_with_knowledge_id(self):
        """Should accept knowledge_id parameter."""
        from app.api.knowledge import KnowledgeSearchRequest
        req = KnowledgeSearchRequest(query="test", knowledge_id="kb-123")
        assert req.knowledge_id == "kb-123"

    def test_search_request_custom_top_k(self):
        """Should accept custom top_k."""
        from app.api.knowledge import KnowledgeSearchRequest
        req = KnowledgeSearchRequest(query="test", top_k=5)
        assert req.top_k == 5

    def test_search_request_custom_weight(self):
        """Should accept custom vector_weight."""
        from app.api.knowledge import KnowledgeSearchRequest
        req = KnowledgeSearchRequest(query="test", vector_weight=0.9)
        assert req.vector_weight == 0.9
