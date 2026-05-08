"""
Skills module with auto-discovery.

New skills are picked up automatically by placing a .py file in this
directory that defines a BaseSkill instance. No manual registration needed.
"""
from app.skills.base import BaseSkill, SkillResult
from app.skills.registry import SkillRegistry, registry

# Auto-discover all skills on first import
registry.discover()

__all__ = [
    "registry",
    "SkillRegistry",
    "BaseSkill",
    "SkillResult",
]
