"""
Image processing API for multimodal understanding.
Supports image upload, OCR, vision understanding, and image description.
"""
import base64
import os
import uuid
from datetime import datetime

import aiofiles
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.auth import TokenData, get_optional_user
from app.core.logger import get_logger
from app.multimodal.ocr import ocr_processor
from app.multimodal.vision import vision_processor

logger = get_logger(__name__)

router = APIRouter()

# Upload directory for images
UPLOAD_DIR = "data/uploads/images"
os.makedirs(UPLOAD_DIR, exist_ok=True)


class ImageUploadResponse(BaseModel):
    image_id: str
    filename: str
    file_path: str
    size: int


class OCRResponse(BaseModel):
    image_id: str
    text: str
    blocks: list[dict]


class VisionResponse(BaseModel):
    image_id: str
    query: str
    answer: str


class ImageDescriptionResponse(BaseModel):
    image_id: str
    description: str
    tags: list[str]


# === Image Upload ===

@router.post("/upload", response_model=ImageUploadResponse)
async def upload_image(
    file: UploadFile = File(...),
    current_user: TokenData | None = Depends(get_optional_user),
):
    """
    Upload an image file.
    Supports: PNG, JPG, JPEG, GIF, BMP, WEBP
    """
    # Validate file type
    ext = os.path.splitext(file.filename)[1].lower()
    allowed_extensions = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}

    if ext not in allowed_extensions:
        raise HTTPException(
            400,
            f"Unsupported image type: {ext}. Allowed: {allowed_extensions}"
        )

    # Check file size (max 20MB for images)
    content = await file.read()
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(413, "Image too large. Maximum size is 20MB")

    # Generate image ID
    image_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{image_id}{ext}")

    # Save file
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(content)

    file_size = len(content)

    logger.info(f"Image uploaded: {image_id}, size: {file_size}")

    return ImageUploadResponse(
        image_id=image_id,
        filename=file.filename,
        file_path=file_path,
        size=file_size,
    )


@router.post("/upload-base64")
async def upload_image_base64(
    image_data: str = Form(...),
    filename: str | None = Form(None),
    current_user: TokenData | None = Depends(get_optional_user),
):
    """
    Upload an image from base64 encoded data.
    Useful for frontend screenshots and clipboard images.
    """
    try:
        # Decode base64
        if "," in image_data:
            # Remove data:image/xxx;base64, prefix
            image_data = image_data.split(",")[1]

        decoded = base64.b64decode(image_data)

        # Detect image type from magic bytes
        if decoded[:8] == b'\x89PNG\r\n\x1a\n':
            ext = ".png"
        elif decoded[:2] == b'\xff\xd8':
            ext = ".jpg"
        elif decoded[:6] in (b'GIF87a', b'GIF89a'):
            ext = ".gif"
        else:
            ext = ".png"  # Default to PNG

        # Save file
        image_id = str(uuid.uuid4())
        file_path = os.path.join(UPLOAD_DIR, f"{image_id}{ext}")

        async with aiofiles.open(file_path, "wb") as f:
            await f.write(decoded)

        return {
            "image_id": image_id,
            "filename": filename or f"image{ext}",
            "file_path": file_path,
            "size": len(decoded),
        }

    except Exception as e:
        raise HTTPException(400, f"Failed to decode image: {e}")


# === OCR Processing ===

@router.post("/ocr", response_model=OCRResponse)
async def extract_text_from_image(
    file: UploadFile = File(...),
    current_user: TokenData | None = Depends(get_optional_user),
):
    """
    Extract text from an image using PaddleOCR.
    Supports Chinese and English text recognition.
    """
    # Save uploaded image
    ext = os.path.splitext(file.filename)[1].lower()
    image_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{image_id}{ext}")

    async with aiofiles.open(file_path, "wb") as f:
        content = await file.read()
        await f.write(content)

    try:
        # Run OCR
        result = await ocr_processor.extract_text_from_image(file_path)

        # Parse OCR result into blocks
        blocks = []
        if hasattr(ocr_processor, 'last_result'):
            for item in ocr_processor.last_result:
                if item:
                    for line in item:
                        blocks.append({
                            "text": line[1][0],
                            "confidence": line[1][1],
                            "bbox": line[0],
                        })

        return OCRResponse(
            image_id=image_id,
            text=result,
            blocks=blocks[:50],  # Limit blocks
        )

    except Exception as e:
        logger.error(f"OCR failed: {e}")
        raise HTTPException(500, "OCR processing failed")


@router.post("/ocr/{image_id}", response_model=OCRResponse)
async def ocr_by_id(
    image_id: str,
    current_user: TokenData | None = Depends(get_optional_user),
):
    """
    Run OCR on a previously uploaded image.
    """
    # Find image file
    for ext in [".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"]:
        file_path = os.path.join(UPLOAD_DIR, f"{image_id}{ext}")
        if os.path.exists(file_path):
            break
    else:
        raise HTTPException(404, "Image not found")

    try:
        result = await ocr_processor.extract_text_from_image(file_path)

        blocks = []
        if hasattr(ocr_processor, 'last_result'):
            for item in ocr_processor.last_result:
                if item:
                    for line in item:
                        blocks.append({
                            "text": line[1][0],
                            "confidence": line[1][1],
                            "bbox": line[0],
                        })

        return OCRResponse(
            image_id=image_id,
            text=result,
            blocks=blocks[:50],
        )

    except Exception:
        raise HTTPException(500, "OCR processing failed")


# === Vision Understanding (GLM-4V) ===

@router.post("/understand", response_model=VisionResponse)
async def understand_image(
    file: UploadFile = File(...),
    query: str = Form("请描述这张图片的内容"),
    current_user: TokenData | None = Depends(get_optional_user),
):
    """
    Understand an image using GLM-4V.
    Ask questions about the image content.
    """
    # Save uploaded image
    ext = os.path.splitext(file.filename)[1].lower()
    image_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{image_id}{ext}")

    async with aiofiles.open(file_path, "wb") as f:
        content = await file.read()
        await f.write(content)

    try:
        answer = await vision_processor.understand_image(file_path, query)

        return VisionResponse(
            image_id=image_id,
            query=query,
            answer=answer,
        )

    except Exception as e:
        logger.error(f"Vision understanding failed: {e}")
        raise HTTPException(500, f"Image understanding failed: {e}")


@router.post("/understand/{image_id}", response_model=VisionResponse)
async def understand_by_id(
    image_id: str,
    query: str = Form("请描述这张图片的内容"),
    current_user: TokenData | None = Depends(get_optional_user),
):
    """
    Ask a question about a previously uploaded image.
    """
    # Find image file
    for ext in [".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"]:
        file_path = os.path.join(UPLOAD_DIR, f"{image_id}{ext}")
        if os.path.exists(file_path):
            break
    else:
        raise HTTPException(404, "Image not found")

    try:
        answer = await vision_processor.understand_image(file_path, query)

        return VisionResponse(
            image_id=image_id,
            query=query,
            answer=answer,
        )

    except Exception as e:
        raise HTTPException(500, f"Image understanding failed: {e}")


# === Image Description ===

@router.post("/describe", response_model=ImageDescriptionResponse)
async def describe_image(
    file: UploadFile = File(...),
    current_user: TokenData | None = Depends(get_optional_user),
):
    """
    Generate a detailed description of an image.
    Useful for building image-based knowledge base.
    """
    # Save uploaded image
    ext = os.path.splitext(file.filename)[1].lower()
    image_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{image_id}{ext}")

    async with aiofiles.open(file_path, "wb") as f:
        content = await file.read()
        await f.write(content)

    try:
        description = await vision_processor.describe_image(file_path)

        # Extract tags from description (simple keyword extraction)
        tags = []
        keywords = ["图表", "流程图", "架构图", "代码", "表格", "文档", "截图",
                    "界面", "logo", "图片", "照片", "示意图", "数据"]
        for kw in keywords:
            if kw in description:
                tags.append(kw)

        return ImageDescriptionResponse(
            image_id=image_id,
            description=description,
            tags=tags,
        )

    except Exception as e:
        logger.error(f"Image description failed: {e}")
        raise HTTPException(500, f"Image description failed: {e}")


# === PDF OCR (for scanned documents) ===

@router.post("/pdf-ocr")
async def ocr_pdf(
    file: UploadFile = File(...),
    current_user: TokenData | None = Depends(get_optional_user),
):
    """
    Extract text from a scanned PDF using OCR.
    Returns text for each page.
    """
    ext = os.path.splitext(file.filename)[1].lower()
    if ext != ".pdf":
        raise HTTPException(400, "Only PDF files are supported")

    # Save PDF
    pdf_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{pdf_id}.pdf")

    async with aiofiles.open(file_path, "wb") as f:
        content = await file.read()
        await f.write(content)

    try:
        pages = await ocr_processor.extract_text_from_pdf(file_path)

        return {
            "pdf_id": pdf_id,
            "pages": [
                {
                    "page": p["page"],
                    "text": p["text"],
                    "tables": p.get("tables", []),
                }
                for p in pages
            ],
            "total_pages": len(pages),
        }

    except Exception as e:
        logger.error(f"PDF OCR failed: {e}")
        raise HTTPException(500, f"PDF OCR failed: {e}")


# === Batch Processing ===

@router.post("/batch-ocr")
async def batch_ocr(
    files: list[UploadFile] = File(...),
    current_user: TokenData | None = Depends(get_optional_user),
):
    """
    Run OCR on multiple images in batch.
    """
    results = []

    for file in files:
        ext = os.path.splitext(file.filename)[1].lower()
        image_id = str(uuid.uuid4())
        file_path = os.path.join(UPLOAD_DIR, f"{image_id}{ext}")

        async with aiofiles.open(file_path, "wb") as f:
            content = await file.read()
            await f.write(content)

        try:
            text = await ocr_processor.extract_text_from_image(file_path)
            results.append({
                "image_id": image_id,
                "filename": file.filename,
                "text": text,
                "success": True,
            })
        except Exception as e:
            results.append({
                "image_id": image_id,
                "filename": file.filename,
                "text": "",
                "success": False,
                "error": str(e),
            })

    return {"results": results}


# === Image Info ===

@router.get("/{image_id}/info")
async def get_image_info(
    image_id: str,
    current_user: TokenData | None = Depends(get_optional_user),
):
    """
    Get information about an uploaded image.
    """
    # Find image file
    for ext in [".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"]:
        file_path = os.path.join(UPLOAD_DIR, f"{image_id}{ext}")
        if os.path.exists(file_path):
            break
    else:
        raise HTTPException(404, "Image not found")

    # Get file stats
    stat = os.stat(file_path)

    return {
        "image_id": image_id,
        "file_path": file_path,
        "size": stat.st_size,
        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
    }


@router.delete("/{image_id}")
async def delete_image(
    image_id: str,
    current_user: TokenData | None = Depends(get_optional_user),
):
    """
    Delete an uploaded image.
    """
    deleted = False

    for ext in [".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"]:
        file_path = os.path.join(UPLOAD_DIR, f"{image_id}{ext}")
        if os.path.exists(file_path):
            os.remove(file_path)
            deleted = True
            break

    if not deleted:
        raise HTTPException(404, "Image not found")

    return {"status": "deleted", "image_id": image_id}
