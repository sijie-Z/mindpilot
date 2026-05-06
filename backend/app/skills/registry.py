"""
Skill registry for managing and executing skills.
"""
from typing import Any

from app.skills.base import BaseSkill, SkillResult
from app.skills.calc_skill import calc_skill
from app.skills.image_skill import image_skill
from app.skills.rag_skill import rag_skill
from app.skills.search_skill import search_skill


class SkillRegistry:
    """Registry for all available skills."""

    def __init__(self):
        self._skills: dict[str, BaseSkill] = {}

    def register(self, skill: BaseSkill):
        """Register a skill."""
        self._skills[skill.name] = skill

    def unregister(self, name: str):
        """Unregister a skill."""
        if name in self._skills:
            del self._skills[name]

    def get(self, name: str) -> BaseSkill | None:
        """Get a skill by name."""
        return self._skills.get(name)

    def list_skills(self) -> list[dict[str, Any]]:
        """List all registered skills."""
        return [skill.to_dict() for skill in self._skills.values()]

    async def execute(
        self,
        name: str,
        query: str,
        context: dict[str, Any] | None = None,
    ) -> SkillResult:
        """Execute a skill by name."""
        skill = self.get(name)
        if not skill:
            return SkillResult(
                success=False,
                error=f"Skill not found: {name}",
            )
        return await skill.execute(query, context)

    def get_skill_for_intent(self, intent: str) -> str | None:
        """Map intent to skill name."""
        mapping = {
            "doc_qa": "doc_qa",
            "search": "web_search",
            "calculation": "calculator",
            "image": "image_understanding",
        }
        return mapping.get(intent)


# Global registry
registry = SkillRegistry()

# Register default skills
registry.register(search_skill)
registry.register(rag_skill)
registry.register(calc_skill)
registry.register(image_skill)
