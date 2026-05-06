"""
Vision processor using Zhipu GLM-4V via async LLM client.
"""
import asyncio
import base64
from pathlib import Path

from app.core.llm_client import AsyncLLMClient
from app.core.logger import get_logger

logger = get_logger(__name__)


class VisionProcessor:
    """Async vision processor for image understanding using VLM."""

    def __init__(self, llm: AsyncLLMClient | None = None, model: str = "glm-4v-plus"):
        self.llm = llm or AsyncLLMClient()
        self.model = model

    async def understand_image(self, image_path: str, query: str) -> str:
        """Understand image content and answer a question about it."""
        image_b64 = await self._encode_image(image_path)
        mime = self._get_mime(image_path)

        return await self.llm.chat(
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{image_b64}"}},
                    {"type": "text", "text": query},
                ],
            }],
            model=self.model,
        )

    async def understand_image_base64(self, image_base64: str, query: str, mime: str = "image/png") -> str:
        """Understand image from base64 data."""
        return await self.llm.chat(
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{image_base64}"}},
                    {"type": "text", "text": query},
                ],
            }],
            model=self.model,
        )

    async def describe_image(self, image_path: str) -> str:
        """Generate detailed description for knowledge base indexing."""
        return await self.understand_image(
            image_path,
            "请详细描述这张图片的内容，包括文字、图表、结构、布局等所有可见信息。"
        )

    async def describe_image_base64(self, image_base64: str) -> str:
        """Generate description from base64 image data."""
        return await self.understand_image_base64(
            image_base64,
            "请详细描述这张图片的内容，包括文字、图表、结构、布局等所有可见信息。"
        )

    async def analyze_error_screenshot(self, image_path: str) -> str:
        return await self.understand_image(
            image_path,
            "请分析这张截图中的报错信息，说明错误原因和可能的解决方案。"
        )

    async def analyze_architecture_diagram(self, image_path: str) -> str:
        return await self.understand_image(
            image_path,
            "请分析这张架构图/流程图，描述系统结构和各组件之间的关系。"
        )

    async def _encode_image(self, image_path: str) -> str:
        loop = asyncio.get_running_loop()
        with open(image_path, "rb") as f:
            data = await loop.run_in_executor(None, f.read)
        return base64.b64encode(data).decode()

    @staticmethod
    def _get_mime(image_path: str) -> str:
        ext = Path(image_path).suffix.lower()
        return {
            ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp",
        }.get(ext, "image/png")
