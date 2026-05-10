"""
Image understanding skill using VLM.

Uses Zhipu GLM-4V for image analysis. Client is reused across calls.
Auto-discovered by the skill registry.
"""
from __future__ import annotations

import asyncio
import base64
from typing import Any

from app.config import settings
from app.skills.base import BaseSkill, SkillResult

# Reuse a single client instance
_client = None


def _get_client():
    global _client
    if _client is None:
        from zhipuai import ZhipuAI
        _client = ZhipuAI(api_key=settings.ZHIPU_API_KEY)
    return _client


class ImageSkill(BaseSkill):
    """Skill for understanding and analyzing images via GLM-4V."""

    def __init__(self) -> None:
        super().__init__(
            name="image_understanding",
            description="理解图片内容并回答问题（GLM-4V）",
        )

    async def execute(
        self,
        query: str,
        context: dict[str, Any] | None = None,
    ) -> SkillResult:
        """Understand image content and answer questions."""
        ctx = context or {}
        image_base64 = ctx.get("image_base64", "")
        image_path = ctx.get("image_path", "")

        if not image_base64 and not image_path:
            return SkillResult(success=False, error="没有提供图片")

        try:
            # Read from file if base64 not provided directly
            if not image_base64 and image_path:
                with open(image_path, "rb") as f:
                    image_base64 = base64.b64encode(f.read()).decode()

            client = _get_client()
            loop = asyncio.get_running_loop()

            response = await loop.run_in_executor(
                None,
                lambda: client.chat.completions.create(
                    model="glm-4v-plus",
                    messages=[{
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{image_base64}",
                                },
                            },
                            {"type": "text", "text": query},
                        ],
                    }],
                ),
            )

            answer = response.choices[0].message.content
            return SkillResult(
                success=True,
                result=answer,
                metadata={"model": "glm-4v-plus"},
            )

        except Exception as e:
            return SkillResult(success=False, error=str(e))


# Module-level instance for auto-discovery
image_skill = ImageSkill()
