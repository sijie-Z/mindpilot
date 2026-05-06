"""
RAG skill for document-based question answering.
"""
from app.agents.answer_agent import generate_answer
from app.rag.retriever import retriever
from app.skills.base import BaseSkill, SkillResult


class RAGSkill(BaseSkill):
    """Skill for RAG-based document question answering."""

    def __init__(self):
        super().__init__(
            name="doc_qa",
            description="Answer questions based on uploaded documents using RAG"
        )

    async def execute(
        self,
        query: str,
        context: dict = None,
    ) -> SkillResult:
        """Execute RAG query."""
        try:
            context = context or {}
            knowledge_id = context.get("knowledge_id", "")

            # Hybrid retrieval
            docs = await retriever.search(
                query=query,
                knowledge_id=knowledge_id,
                top_k=10,
            )

            if not docs:
                return SkillResult(
                    success=True,
                    result="没有在知识库中找到相关文档。",
                    metadata={"query": query}
                )

            # Generate answer
            answer = await generate_answer(query, docs)

            # Extract sources
            sources = [
                {
                    "filename": doc.get("metadata", {}).get("filename", "未知"),
                    "page": doc.get("metadata", {}).get("page"),
                    "score": doc.get("score", 0),
                }
                for doc in docs[:3]
            ]

            return SkillResult(
                success=True,
                result=answer,
                metadata={
                    "query": query,
                    "doc_count": len(docs),
                    "sources": sources,
                }
            )

        except Exception as e:
            return SkillResult(
                success=False,
                error=str(e),
            )


# Global instance
rag_skill = RAGSkill()
