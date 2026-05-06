"""
Multimodal processing module.
"""
from app.multimodal.ocr import OCRProcessor, ocr_processor
from app.multimodal.vision import VisionProcessor, vision_processor

__all__ = [
    "ocr_processor",
    "OCRProcessor",
    "vision_processor",
    "VisionProcessor",
]
