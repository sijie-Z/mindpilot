"""
Image understanding skill using VLM.
"""
import base64

from zhipuai import ZhipuAI

from app.config import settings
from app.skills.base import BaseSkill, SkillResult


class ImageSkill(BaseSkill):
    """Skill for understanding and analyzing images."""

    def __init__(self):
        super().__init__(
            name="image_understanding",
            description="Understand and answer questions about images"
        )

    async def execute(
        self,
        query: str,
        context: dict = None,
    ) -> SkillResult:
        """Understand image content and answer questions."""
        try:
            context = context or {}
            image_path = context.get("image_path", "")

            if not image_path:
                return SkillResult(
                    success=False,
                    error="没有提供图片路径",
                )

            # Read image and convert to base64
            with open(image_path, "rb") as f:
                image_base64 = base64.b64encode(f.read()).decode()

            # Use Zhipu GLM-4V for image understanding
            client = ZhipuAI(api_key=settings.ZHIPU_API_KEY)

            response = client.chat.completions.create(
                model="glm-4v-plus",
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_base64}"
                            }
                        },
                        {
                            "type": "text",
                            "text": query
                        }
                    ]
                }]
            )

            answer = response.choices[0].message.content

            return SkillResult(
                success=True,
                result=answer,
                metadata={
                    "image_path": image_path,
                    "model": "glm-4v-plus",
                }
            )

        except Exception as e:
            return SkillResult(
                success=False,
                error=str(e),
            )


# Global instance
image_skill = ImageSkill()
