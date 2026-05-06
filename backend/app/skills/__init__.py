"""
Skills module initialization.
"""
from app.skills.base import BaseSkill, SkillResult
from app.skills.calc_skill import calc_skill
from app.skills.image_skill import image_skill
from app.skills.rag_skill import rag_skill
from app.skills.registry import SkillRegistry, registry
from app.skills.search_skill import search_skill

__all__ = [
    "registry",
    "SkillRegistry",
    "BaseSkill",
    "SkillResult",
    "search_skill",
    "rag_skill",
    "calc_skill",
    "image_skill",
]
