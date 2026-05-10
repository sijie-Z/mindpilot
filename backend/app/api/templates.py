"""
Prompt template API for quick chat input.
Supports built-in templates and user-created custom templates.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from app.auth import TokenData, get_current_user, get_optional_user
from app.core.logger import get_logger
from app.storage.database import get_db_session

logger = get_logger(__name__)
router = APIRouter()

# ── Built-in templates ──

BUILTIN_TEMPLATES = [
    {
        "title": "文档总结",
        "content": "请对以下文档内容进行总结，提取关键信息和要点：\n\n",
        "category": "analysis",
    },
    {
        "title": "翻译为中文",
        "content": "请将以下内容翻译为中文，保持原文的语气和风格：\n\n",
        "category": "translate",
    },
    {
        "title": "翻译为英文",
        "content": "Please translate the following content into English, maintaining the original tone and style:\n\n",
        "category": "translate",
    },
    {
        "title": "代码解释",
        "content": "请解释以下代码的功能和逻辑，逐行说明：\n\n```\n\n```",
        "category": "code",
    },
    {
        "title": "代码优化",
        "content": "请分析以下代码，提出优化建议，包括性能、可读性和最佳实践方面：\n\n```\n\n```",
        "category": "code",
    },
    {
        "title": "数据分析",
        "content": "请分析以下数据，提取关键指标和趋势，并给出洞察建议：\n\n",
        "category": "analysis",
    },
    {
        "title": "写作润色",
        "content": "请对以下文本进行润色，改进表达、修正语法错误，保持原意：\n\n",
        "category": "writing",
    },
    {
        "title": "会议纪要",
        "content": "请根据以下会议内容，整理成结构化的会议纪要，包括：议题、讨论要点、决议和待办事项：\n\n",
        "category": "writing",
    },
    {
        "title": "对比分析",
        "content": "请对比分析以下两个方案/产品的优缺点，给出推荐建议：\n\n方案A：\n\n方案B：",
        "category": "analysis",
    },
    {
        "title": "Bug 排查",
        "content": "请帮我排查以下问题，分析可能的原因并给出解决方案：\n\n**现象描述：**\n\n**复现步骤：**\n\n**错误日志：**\n\n```\n\n```",
        "category": "code",
    },
]


class TemplateCreate(BaseModel):
    title: str
    content: str
    category: str = "general"


class TemplateUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    category: str | None = None


async def _ensure_builtin_templates():
    """Seed built-in templates if they don't exist."""
    async with get_db_session() as db:
        result = await db.execute(
            text("SELECT COUNT(*) FROM prompt_templates WHERE is_builtin = 1")
        )
        count = result.scalar()
        if count == 0:
            for tpl in BUILTIN_TEMPLATES:
                await db.execute(
                    text("INSERT INTO prompt_templates (id, title, content, category, is_builtin) "
                         "VALUES (UUID(), :title, :content, :category, 1)"),
                    tpl,
                )
            logger.info("Seeded built-in prompt templates", count=len(BUILTIN_TEMPLATES))


@router.get("/")
async def list_templates(
    category: str | None = None,
    current_user: TokenData | None = Depends(get_optional_user),
):
    """List all available templates (built-in + user's custom)."""
    await _ensure_builtin_templates()

    user_id = current_user.user_id if current_user else None

    async with get_db_session() as db:
        if category:
            result = await db.execute(
                text("SELECT id, title, content, category, is_builtin, user_id "
                     "FROM prompt_templates WHERE category = :cat AND (is_builtin = 1 OR user_id = :uid) "
                     "ORDER BY is_builtin DESC, created_at DESC"),
                {"cat": category, "uid": user_id},
            )
        else:
            result = await db.execute(
                text("SELECT id, title, content, category, is_builtin, user_id "
                     "FROM prompt_templates WHERE is_builtin = 1 OR user_id = :uid "
                     "ORDER BY is_builtin DESC, category, created_at DESC"),
                {"uid": user_id},
            )

        rows = result.fetchall()
        return {
            "templates": [
                {
                    "id": r[0],
                    "title": r[1],
                    "content": r[2],
                    "category": r[3],
                    "is_builtin": bool(r[4]),
                    "is_owner": r[5] == user_id if user_id else False,
                }
                for r in rows
            ]
        }


@router.post("/")
async def create_template(
    req: TemplateCreate,
    current_user: TokenData = Depends(get_current_user),
):
    """Create a custom template."""
    user_id = current_user.user_id

    async with get_db_session() as db:
        result = await db.execute(
            text("INSERT INTO prompt_templates (id, user_id, title, content, category, is_builtin) "
                 "VALUES (UUID(), :uid, :title, :content, :cat, 0)"),
            {"uid": user_id, "title": req.title, "content": req.content, "cat": req.category},
        )

        # Get the inserted ID
        result = await db.execute(
            text("SELECT id FROM prompt_templates WHERE user_id = :uid ORDER BY created_at DESC LIMIT 1"),
            {"uid": user_id},
        )
        row = result.fetchone()

    return {"id": row[0], "title": req.title, "content": req.content, "category": req.category}


@router.put("/{template_id}")
async def update_template(
    template_id: str,
    req: TemplateUpdate,
    current_user: TokenData = Depends(get_current_user),
):
    """Update a custom template (only owner can update)."""
    user_id = current_user.user_id

    async with get_db_session() as db:
        # Verify ownership
        result = await db.execute(
            text("SELECT user_id, is_builtin FROM prompt_templates WHERE id = :tid"),
            {"tid": template_id},
        )
        row = result.fetchone()
        if not row:
            raise HTTPException(404, "Template not found")
        if row[1]:  # is_builtin
            raise HTTPException(403, "Cannot modify built-in templates")
        if row[0] != user_id:
            raise HTTPException(403, "Not your template")

        updates = {}
        if req.title is not None:
            updates["title"] = req.title
        if req.content is not None:
            updates["content"] = req.content
        if req.category is not None:
            updates["category"] = req.category

        if not updates:
            raise HTTPException(400, "No fields to update")

        set_clause = ", ".join(f"{k} = :{k}" for k in updates)
        await db.execute(
            text(f"UPDATE prompt_templates SET {set_clause} WHERE id = :tid"),
            {**updates, "tid": template_id},
        )

    return {"status": "updated", "id": template_id}


@router.delete("/{template_id}")
async def delete_template(
    template_id: str,
    current_user: TokenData = Depends(get_current_user),
):
    """Delete a custom template (only owner can delete)."""
    user_id = current_user.user_id

    async with get_db_session() as db:
        result = await db.execute(
            text("SELECT user_id, is_builtin FROM prompt_templates WHERE id = :tid"),
            {"tid": template_id},
        )
        row = result.fetchone()
        if not row:
            raise HTTPException(404, "Template not found")
        if row[1]:
            raise HTTPException(403, "Cannot delete built-in templates")
        if row[0] != user_id:
            raise HTTPException(403, "Not your template")

        await db.execute(
            text("DELETE FROM prompt_templates WHERE id = :tid"),
            {"tid": template_id},
        )

    return {"status": "deleted", "id": template_id}
