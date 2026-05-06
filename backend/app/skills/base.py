"""
Base class for all skills.
"""
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel


class SkillResult(BaseModel):
    """Result returned by a skill."""
    success: bool
    result: Any = None
    error: str | None = None
    metadata: dict[str, Any] = {}


class BaseSkill(ABC):
    """Abstract base class for all skills."""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    @abstractmethod
    async def execute(
        self,
        query: str,
        context: dict[str, Any] | None = None,
    ) -> SkillResult:
        """
        Execute the skill with given query and context.

        Args:
            query: The user's query
            context: Additional context (session info, user preferences, etc.)

        Returns:
            SkillResult with execution outcome
        """
        pass

    def to_dict(self) -> dict[str, Any]:
        """Convert skill to dictionary for registration."""
        return {
            "name": self.name,
            "description": self.description,
        }
