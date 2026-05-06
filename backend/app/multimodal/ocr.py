"""
OCR processor using PaddleOCR with async thread-pool execution.
"""
import asyncio
import os
from typing import Any

from app.core.logger import get_logger

logger = get_logger(__name__)


class OCRProcessor:
    """Async OCR processor for scanned documents and images."""

    def __init__(self, lang: str = "ch"):
        self.lang = lang
        self._ocr = None

    def _get_ocr(self):
        """Lazy-load PaddleOCR model."""
        if self._ocr is None:
            from paddleocr import PaddleOCR
            self._ocr = PaddleOCR(use_angle_cls=True, lang=self.lang, show_log=False)
        return self._ocr

    async def extract_text_from_image(self, image_path: str) -> str:
        """Extract text from an image via OCR. Runs PaddleOCR in thread pool."""
        ocr = self._get_ocr()
        loop = asyncio.get_running_loop()

        result = await loop.run_in_executor(None, lambda: ocr.ocr(image_path, cls=True))

        text_lines = []
        for line in result or []:
            for item in line or []:
                text_lines.append(item[1][0])
        return "\n".join(text_lines)

    async def extract_text_from_pdf(self, pdf_path: str) -> list[dict[str, Any]]:
        """Extract text from PDF, using OCR for scanned pages."""
        import fitz

        loop = asyncio.get_running_loop()

        def _process():
            doc = fitz.open(pdf_path)
            pages = []
            for i, page in enumerate(doc):
                text = page.get_text()
                if text.strip():
                    pages.append({"page": i + 1, "text": text, "method": "direct"})
                else:
                    pix = page.get_pixmap(dpi=300)
                    img_path = f"/tmp/pdf_page_{i}.png"
                    pix.save(img_path)
                    ocr_result = self._get_ocr().ocr(img_path, cls=True)
                    lines = []
                    for line in ocr_result or []:
                        for item in line or []:
                            lines.append(item[1][0])
                    pages.append({"page": i + 1, "text": "\n".join(lines), "method": "ocr"})
                    if os.path.exists(img_path):
                        os.remove(img_path)
            return pages

        return await loop.run_in_executor(None, _process)

    async def extract_tables_from_image(self, image_path: str) -> list[list[list[str]]]:
        """Extract tables from image."""
        # Placeholder — full table extraction would use a dedicated model
        text = await self.extract_text_from_image(image_path)
        return [[[text]]] if text else []
