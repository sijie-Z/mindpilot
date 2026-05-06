"""
Tests for skills system and auth module.
"""

import pytest


class TestSkillBase:
    """Tests for base skill class."""

    def test_skill_result_model(self):
        """Test SkillResult model."""
        from app.skills.base import SkillResult

        result = SkillResult(success=True, result="test_output")
        assert result.success is True
        assert result.result == "test_output"

        error_result = SkillResult(success=False, error="Something went wrong")
        assert error_result.success is False
        assert error_result.error == "Something went wrong"

    def test_skill_result_metadata(self):
        """Test SkillResult with metadata."""
        from app.skills.base import SkillResult

        result = SkillResult(
            success=True,
            result="42",
            metadata={"latency_ms": 150, "source": "calc"}
        )
        assert result.metadata["latency_ms"] == 150

    def test_base_skill_to_dict(self):
        """Test skill serialization."""
        from app.skills.calc_skill import calc_skill

        d = calc_skill.to_dict()
        assert d["name"] == "calculator"
        assert "description" in d


class TestCalcSkill:
    """Tests for calculator skill."""

    def test_safe_eval_basic_math(self):
        """Test safe_eval with basic arithmetic."""
        from app.skills.calc_skill import CalcSkill

        calc = CalcSkill()
        assert calc._safe_eval("2 + 2") == 4
        assert calc._safe_eval("10 - 5") == 5
        assert calc._safe_eval("3 * 7") == 21
        assert calc._safe_eval("100 / 4") == 25
        assert calc._safe_eval("2 ** 10") == 1024

    def test_safe_eval_floats(self):
        """Test safe_eval with floating point."""
        from app.skills.calc_skill import CalcSkill

        calc = CalcSkill()
        result = calc._safe_eval("3.14 * 2")
        assert abs(result - 6.28) < 0.01

    def test_safe_eval_parentheses(self):
        """Test safe_eval with parentheses."""
        from app.skills.calc_skill import CalcSkill

        calc = CalcSkill()
        assert calc._safe_eval("(2 + 3) * 4") == 20

    def test_safe_eval_rejects_import(self):
        """Test _safe_eval blocks dangerous expressions."""
        from app.skills.calc_skill import CalcSkill

        calc = CalcSkill()
        dangerous = [
            "__import__('os').system('ls')",
            "open('/etc/passwd')",
            "eval('2+2')",
            "exec('x=1')",
            "globals()",
            "locals()",
            "getattr(__builtins__, 'open')",
            "__builtins__",
        ]
        for expr in dangerous:
            with pytest.raises(Exception):
                calc._safe_eval(expr)

    @pytest.mark.asyncio
    async def test_execute_simple(self):
        """Test execute with simple expression."""
        from app.skills.calc_skill import calc_skill

        result = await calc_skill.execute("2 + 2")
        assert result.success is True
        assert "4" in result.result


class TestSkillRegistry:
    """Tests for skill registry."""

    def test_register_and_get_skill(self):
        """Test registering and retrieving a skill."""
        from app.skills.registry import registry

        # calculator should already be registered
        skill = registry.get("calculator")
        assert skill is not None
        assert skill.name == "calculator"

    def test_get_nonexistent_skill(self):
        """Test getting a non-existent skill returns None."""
        from app.skills.registry import registry

        result = registry.get("nonexistent_skill_xyz")
        assert result is None

    def test_list_skills(self):
        """Test listing all registered skills."""
        from app.skills.registry import registry

        skills = registry.list_skills()
        assert isinstance(skills, list)
        assert len(skills) >= 1
        # Each should be a dict with name and description
        for s in skills:
            assert "name" in s
            assert "description" in s

    def test_execute_registered_skill(self):
        """Test executing a skill through registry."""
        import asyncio

        from app.skills.registry import registry

        actual = asyncio.run(registry.execute("calculator", "2 + 2"))
        assert actual.success is True

    def test_execute_nonexistent_skill(self):
        """Test executing non-existent skill returns error."""
        import asyncio

        from app.skills.registry import registry

        actual = asyncio.run(registry.execute("no_such_skill", "query"))
        assert actual.success is False
        assert "not found" in actual.error.lower()

    def test_get_skill_for_intent(self):
        """Test intent-to-skill mapping."""
        from app.skills.registry import registry

        assert registry.get_skill_for_intent("calculation") == "calculator"
        assert registry.get_skill_for_intent("search") == "web_search"
        assert registry.get_skill_for_intent("unknown_intent") is None

    def test_unregister_skill(self):
        """Test unregistering a skill."""
        from app.skills.base import BaseSkill
        from app.skills.registry import registry

        class TempSkill(BaseSkill):
            async def execute(self, query, context=None):
                from app.skills.base import SkillResult
                return SkillResult(success=True, result="temp")

        skill = TempSkill(name="temp_unreg_test", description="temp")
        registry.register(skill)
        assert registry.get("temp_unreg_test") is not None

        registry.unregister("temp_unreg_test")
        assert registry.get("temp_unreg_test") is None


class TestAuth:
    """Tests for authentication module."""

    def test_auth_handler_create_token(self):
        """Test JWT token creation."""
        from app.auth import AuthHandler

        handler = AuthHandler()
        token = handler.create_access_token(
            data={"user_id": "user-123", "username": "testuser"},
        )
        assert token is not None
        assert len(token) > 20
        assert token.count(".") == 2  # JWT format

    def test_auth_handler_verify_token(self):
        """Test JWT token verification."""
        from app.auth import AuthHandler

        handler = AuthHandler()
        token = handler.create_access_token(
            data={"user_id": "user-456", "username": "verify_test"},
        )
        token_data = handler.verify_token(token)

        assert token_data is not None
        assert token_data.username == "verify_test"

    def test_auth_handler_invalid_token(self):
        """Test invalid token raises HTTPException."""
        from fastapi import HTTPException

        from app.auth import AuthHandler

        handler = AuthHandler()
        with pytest.raises(HTTPException) as exc_info:
            handler.verify_token("invalid.token.here")
        assert exc_info.value.status_code == 401

    def test_token_data_model(self):
        """Test TokenData model."""
        from app.auth import TokenData

        data = TokenData(user_id="u1", username="john", role="admin")
        assert data.user_id == "u1"
        assert data.role == "admin"

        default_data = TokenData()
        assert default_data.role == "user"


class TestConfig:
    """Tests for application config."""

    def test_settings_loaded(self):
        """Test settings are loaded."""
        from app.config import settings

        assert settings.APP_NAME == "MindPilot"

    def test_settings_defaults(self):
        """Test settings have expected defaults."""
        from app.config import settings

        assert hasattr(settings, "DEBUG")
        assert hasattr(settings, "SECRET_KEY")
        assert hasattr(settings, "MYSQL_URL")
        assert hasattr(settings, "REDIS_URL")
        assert hasattr(settings, "VECTOR_STORE")

    def test_settings_values(self):
        """Test specific setting values."""
        from app.config import settings

        assert isinstance(settings.DEBUG, bool)
        assert len(settings.SECRET_KEY) > 0
