"""
Skill registry with auto-discovery and usage telemetry.

Inspired by Hermes Agent's tools/registry.py pattern:
- Auto-discovery eliminates manual import lists
- Usage telemetry tracks call counts, latency, success rates
- Intent-to-skill routing with confidence scoring
- Single source of truth for all skill operations
"""
import importlib
import os
import time
from typing import Any

from app.core.logger import get_logger
from app.skills.base import BaseSkill, SkillResult

logger = get_logger(__name__)

# Intent -> skill mapping with confidence thresholds
INTENT_SKILL_MAP: dict[str, str] = {
    "doc_qa": "doc_qa",
    "search": "web_search",
    "calculation": "calculator",
    "image": "image_understanding",
    "code": "code_executor",
    "analysis": "data_analysis",
}


class SkillRegistry:
    """
    Central registry for all skills with auto-discovery and telemetry.

    Features:
    - Auto-discovery: scans skills/ directory for BaseSkill subclasses
    - Telemetry: tracks call count, success rate, avg latency per skill
    - Intent routing: maps intents to appropriate skills
    - Lifecycle: register, unregister, list, get stats

    Usage:
        # Auto-discover all skills (called once at startup)
        registry.discover()

        # Execute with automatic telemetry
        result = await registry.execute("doc_qa", query, context)

        # Get performance stats
        stats = registry.get_stats()
    """

    def __init__(self):
        self._skills: dict[str, BaseSkill] = {}
        self._stats: dict[str, dict[str, Any]] = {}
        self._discovered = False

    def register(self, skill: BaseSkill) -> None:
        """Register a skill instance."""
        if skill.name in self._skills:
            logger.warning("Skill already registered, overwriting", skill=skill.name)
        self._skills[skill.name] = skill
        self._stats[skill.name] = {
            "call_count": 0,
            "success_count": 0,
            "failure_count": 0,
            "total_latency_ms": 0,
            "last_called_at": None,
        }
        logger.debug("Skill registered", skill=skill.name)

    def unregister(self, name: str) -> None:
        """Unregister a skill."""
        self._skills.pop(name, None)
        self._stats.pop(name, None)

    def get(self, name: str) -> BaseSkill | None:
        """Get a skill by name."""
        return self._skills.get(name)

    def get_for_intent(self, intent: str) -> BaseSkill | None:
        """Get the appropriate skill for a given intent."""
        skill_name = INTENT_SKILL_MAP.get(intent)
        if skill_name:
            return self._skills.get(skill_name)
        return None

    def list_skills(self) -> list[dict[str, Any]]:
        """List all registered skills with metadata and stats."""
        return [
            {
                "name": s.name,
                "description": s.description,
                "stats": self._stats.get(s.name, {}),
            }
            for s in self._skills.values()
        ]

    def get_names(self) -> list[str]:
        """Get all registered skill names."""
        return list(self._skills.keys())

    async def execute(
        self,
        skill_name: str,
        query: str,
        context: dict[str, Any] | None = None,
        session_id: str | None = None,
    ) -> SkillResult:
        """
        Execute a skill by name with automatic telemetry tracking.

        Tracks: call count, success/failure, latency per invocation.
        Persists to skill_logs table for historical analytics.
        """
        skill = self._skills.get(skill_name)
        if not skill:
            return SkillResult(
                success=False,
                error=f"Unknown skill: {skill_name}",
            )

        stats = self._stats[skill_name]
        stats["call_count"] += 1
        stats["last_called_at"] = time.time()

        start = time.monotonic()
        try:
            result = await skill.execute(query, context)
            latency_ms = int((time.monotonic() - start) * 1000)
            stats["total_latency_ms"] += latency_ms

            if result.success:
                stats["success_count"] += 1
            else:
                stats["failure_count"] += 1

            logger.info(
                "Skill executed",
                skill=skill_name,
                success=result.success,
                latency_ms=latency_ms,
            )

            # Persist to database (fire-and-forget)
            self._persist_log(skill_name, query, result, latency_ms, session_id)

            return result

        except Exception as e:
            latency_ms = int((time.monotonic() - start) * 1000)
            stats["total_latency_ms"] += latency_ms
            stats["failure_count"] += 1
            logger.error("Skill execution failed", skill=skill_name, error=str(e))
            self._persist_log(skill_name, query, SkillResult(success=False, error=str(e)), latency_ms, session_id)
            return SkillResult(success=False, error=str(e))

    def _persist_log(
        self,
        skill_name: str,
        query: str,
        result: SkillResult,
        latency_ms: int,
        session_id: str | None,
    ) -> None:
        """Persist skill execution log to database (fire-and-forget)."""
        try:
            import uuid
            from sqlalchemy import text
            from app.storage.database import get_db_session
            import json

            async def _write():
                try:
                    async with get_db_session() as db:
                        await db.execute(
                            text(
                                "INSERT INTO skill_logs (id, session_id, skill_name, input_params, "
                                "output_result, latency_ms, success, error_message) "
                                "VALUES (:id, :sid, :name, :input, :output, :lat, :ok, :err)"
                            ),
                            {
                                "id": str(uuid.uuid4()),
                                "sid": session_id,
                                "name": skill_name,
                                "input": json.dumps({"query": query[:500]}, ensure_ascii=False),
                                "output": json.dumps({"success": result.success}, ensure_ascii=False),
                                "lat": latency_ms,
                                "ok": result.success,
                                "err": result.error[:500] if result.error else None,
                            },
                        )
                except Exception:
                    pass  # Don't let DB errors affect skill execution

            import asyncio
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(_write())
            except RuntimeError:
                pass
        except Exception:
            pass  # Telemetry is best-effort

    def get_stats(self) -> dict[str, Any]:
        """
        Get aggregated stats for all skills.

        Returns per-skill: call_count, success_rate, avg_latency_ms, last_called_at.
        """
        result = {}
        for name, stats in self._stats.items():
            call_count = stats["call_count"]
            avg_latency = (
                stats["total_latency_ms"] // call_count
                if call_count > 0
                else 0
            )
            success_rate = (
                stats["success_count"] / call_count
                if call_count > 0
                else 0.0
            )
            result[name] = {
                "call_count": call_count,
                "success_count": stats["success_count"],
                "failure_count": stats["failure_count"],
                "avg_latency_ms": avg_latency,
                "success_rate": round(success_rate, 3),
                "last_called_at": stats["last_called_at"],
            }
        return result

    def discover(self) -> None:
        """
        Auto-discover and register all skills in the skills/ directory.

        Scans for Python files containing BaseSkill subclass instances.
        Skips base.py, registry.py, and __init__.py.

        This replaces manual import lists — new skills are picked up
        automatically just by placing a .py file in the skills/ directory.
        """
        if self._discovered:
            return

        skills_dir = os.path.dirname(__file__)
        for filename in sorted(os.listdir(skills_dir)):
            if filename.startswith("_") or filename in ("base.py", "registry.py"):
                continue
            if not filename.endswith(".py"):
                continue

            module_name = f"app.skills.{filename[:-3]}"
            try:
                module = importlib.import_module(module_name)
                # Find BaseSkill instances in the module
                for attr_name in dir(module):
                    try:
                        attr = getattr(module, attr_name)
                    except (ImportError, AttributeError):
                        continue
                    if isinstance(attr, BaseSkill) and attr.name not in self._skills:
                        self.register(attr)
            except Exception as e:
                logger.warning(
                    "Failed to load skill module",
                    skill_module=module_name,
                    error=str(e),
                )

        self._discovered = True
        logger.info(
            "Skills auto-discovered",
            count=len(self._skills),
            names=self.get_names(),
        )


# Global registry instance
registry = SkillRegistry()
