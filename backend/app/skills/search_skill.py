"""
Search skill for web search.
"""

from app.skills.base import BaseSkill, SkillResult


class SearchSkill(BaseSkill):
    """Skill for searching the web."""

    def __init__(self):
        super().__init__(
            name="web_search",
            description="Search the web for real-time information"
        )

    async def execute(
        self,
        query: str,
        context: dict = None,
    ) -> SkillResult:
        """Execute web search using a browser-like approach."""
        try:
            # Try using Jina AI for web search
            import httpx

            # Use Jina AI for web search/summarization
            url = f"https://s.jina.ai/{query}"
            headers = {
                "Accept": "application/json",
                "X-Engine": "basic",
            }

            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers, timeout=30.0)
                data = response.json()

                results = data.get("results", [])

                if not results:
                    return SkillResult(
                        success=True,
                        result="没有找到相关结果",
                        metadata={"query": query}
                    )

                # Format results
                formatted = []
                for i, item in enumerate(results[:5], 1):
                    title = item.get("title", "无标题")
                    content = item.get("content", "")[:200]
                    url_link = item.get("url", "")
                    formatted.append(f"{i}. **{title}**\n{content}...\n[来源]({url_link})")

                result_text = "\n\n".join(formatted)

                return SkillResult(
                    success=True,
                    result=result_text,
                    metadata={
                        "query": query,
                        "count": len(results),
                    }
                )

        except Exception as e:
            return SkillResult(
                success=False,
                error=str(e),
            )


# Global instance
search_skill = SearchSkill()
