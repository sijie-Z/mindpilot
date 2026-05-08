"""
Document parser for multiple file formats.
Supports PDF, Word, PowerPoint, Markdown, and plain text.
"""
import os
from pathlib import Path
from typing import Any


class DocumentParser:
    """Parse documents into structured content."""

    SUPPORTED_FORMATS = {".pdf", ".docx", ".doc", ".pptx", ".ppt", ".txt", ".md"}

    async def parse(self, file_path: str) -> list[dict[str, Any]]:
        """
        Parse document and return structured pages/sections.

        Returns:
            List of dicts with keys: page, text, tables, images
        """
        ext = Path(file_path).suffix.lower()

        if ext not in self.SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported format: {ext}")

        if ext == ".pdf":
            return await self.parse_pdf(file_path)
        elif ext in (".docx", ".doc"):
            return await self.parse_docx(file_path)
        elif ext in (".pptx", ".ppt"):
            return await self.parse_pptx(file_path)
        elif ext in (".txt", ".md"):
            return await self.parse_text(file_path)

    async def parse_pdf(self, file_path: str) -> list[dict[str, Any]]:
        """Parse PDF document."""
        import pdfplumber

        pages = []
        with pdfplumber.open(file_path) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""

                # Extract tables
                tables = []
                for table in page.extract_tables():
                    table_str = "【表格】\n"
                    for row in table:
                        table_str += " | ".join(
                            str(cell) if cell else "" for cell in row
                        ) + "\n"
                    tables.append(table_str)

                # If no text found, mark for OCR
                needs_ocr = not text.strip()

                pages.append({
                    "page": i + 1,
                    "text": text,
                    "tables": tables,
                    "needs_ocr": needs_ocr,
                })

        return pages

    async def parse_docx(self, file_path: str) -> list[dict[str, Any]]:
        """Parse Word document."""
        from docx import Document

        doc = Document(file_path)
        sections = []
        current_section = {"page": 1, "text": "", "tables": []}

        for para in doc.paragraphs:
            if para.text.strip():
                current_section["text"] += para.text + "\n"

        # Extract tables
        for table in doc.tables:
            table_str = "【表格】\n"
            for row in table.rows:
                table_str += " | ".join(cell.text for cell in row.cells) + "\n"
            current_section["tables"].append(table_str)

        sections.append(current_section)
        return sections

    async def parse_pptx(self, file_path: str) -> list[dict[str, Any]]:
        """Parse PowerPoint document."""
        from pptx import Presentation

        prs = Presentation(file_path)
        slides = []
        current_tables = []  # Track tables for current slide

        for i, slide in enumerate(prs.slides):
            text = ""
            current_tables = []

            for shape in slide.shapes:
                if shape.has_text_frame:
                    for para in shape.text_frame.paragraphs:
                        text += para.text + "\n"

                if shape.has_table:
                    table_str = "【表格】\n"
                    for row in shape.table.rows:
                        table_str += " | ".join(
                            cell.text for cell in row.cells
                        ) + "\n"
                    current_tables.append(table_str)

            slides.append({
                "page": i + 1,
                "text": text,
                "tables": current_tables,
            })

        return slides

    async def parse_text(self, file_path: str) -> list[dict[str, Any]]:
        """Parse plain text or markdown."""
        with open(file_path, encoding="utf-8") as f:
            text = f.read()

        return [{"page": 1, "text": text, "tables": []}]

    async def parse_with_ocr(self, file_path: str) -> list[dict[str, Any]]:
        """Parse scanned PDF using PaddleOCR."""
        import tempfile

        import fitz  # PyMuPDF
        from paddleocr import PaddleOCR

        ocr = PaddleOCR(use_angle_cls=True, lang="ch")
        doc = fitz.open(file_path)
        pages = []

        for i, page in enumerate(doc):
            # Convert page to image
            pix = page.get_pixmap(dpi=300)
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                img_path = tmp.name
            pix.save(img_path)

            # Run OCR
            result = ocr.ocr(img_path, cls=True)
            text = ""
            for line in result:
                for item in line:
                    text += item[1][0] + "\n"

            pages.append({
                "page": i + 1,
                "text": text,
                "tables": [],
            })

            # Cleanup temp file
            os.remove(img_path)

        return pages
