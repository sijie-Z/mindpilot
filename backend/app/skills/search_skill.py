"""
Search skill for web search.

Uses Jina AI for web search with retry and timeout.
Auto-discovered by the skill registry.
"""
from __future__ import annotations

import os
from typing import Any

import httpx

from app.skills.base import BaseSkill, SkillResult

# Configurable via environment
JINA_API_KEY = os.getenv("JINA_API_KEY", "")
SEARCH_TIMEOUT = float(os.getenv("SEARCH_TIMEOUT", "15"))
MAX_RETRIES = 2


class SearchSkill(BaseSkill):
    """Skill for searching the web via Jina AI."""

    def __init__(self) -> None:
        super().__init__(
            name="web_search",
            description="搜索互联网获取实时信息",
        )

    async def execute(
        self,
        query: str,
        context: dict[str, Any] | None = None,
    ) -> SkillResult:
        """Execute web search with retry."""
        if not query.strip():
            return SkillResult(success=False, error="搜索内容不能为空")

        headers = {
            "Accept": "application/json",
            "X-Engine": "basic",
        }
        if JINA_API_KEY:
            headers["Authorization"] = f"Bearer {JINA_API_KEY}"

        url = f"https://s.jina.ai/{query}"
        last_error = None

        for attempt in range(MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        url, headers=headers, timeout=SEARCH_TIMEOUT,
                    )
                    response.raise_for_status()
                    data = response.json()

                results = data.get("data", data.get("results", []))
                if not results:
                    return SkillResult(
                        success=True,
                        result="没有找到相关结果",
                        metadata={"query": query, "count": 0},
                    )

                formatted = []
                for i, item in enumerate(results[:5], 1):
                    title = item.get("title", "无标题")
                    snippet = (item.get("description", "") or item.get("content", ""))[:200]
                    link = item.get("url", "")
                    formatted.append(f"{i}. **{title}**\n{snippet}\n[来源]({link})")

                return SkillResult(
                    success=True,
                    result="\n\n".join(formatted),
                    metadata={"query": query, "count": len(results)},
                )

            except httpx.TimeoutException:
                last_error = "搜索超时，请稍后重试"
            except httpx.HTTPStatusError as e:
                last_error = f"搜索服务返回错误: {e.response.status_code}"
                if e.response.status_code < 500:
                    break  # Client errors won't resolve with retry
            except Exception as e:
                last_error = str(e)

        return SkillResult(success=False, error=last_error or "搜索失败")


# Module-level instance for auto-discovery
search_skill = SearchSkill()
