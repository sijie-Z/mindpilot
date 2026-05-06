"""
API module initialization.
"""
from app.api.chat import router as chat_router
from app.api.document import router as document_router
from app.api.knowledge import router as knowledge_router
from app.api.workflow import router as workflow_router

__all__ = ["chat_router", "document_router", "knowledge_router", "workflow_router"]
