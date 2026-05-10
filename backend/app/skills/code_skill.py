"""
Code execution skill (sandboxed Python eval).

Executes Python expressions in a restricted environment with
timeout protection and dangerous-operation filtering.

Auto-discovered by the skill registry.
"""
from __future__ import annotations

import ast
import math
import re
import signal
import time
from typing import Any

from app.skills.base import BaseSkill, SkillResult

# Restricted builtins for sandboxed execution
_SAFE_BUILTINS = {
    "abs": abs, "all": all, "any": any, "bool": bool,
    "dict": dict, "enumerate": enumerate, "filter": filter,
    "float": float, "format": format, "frozenset": frozenset,
    "int": int, "len": len, "list": list, "map": map,
    "max": max, "min": min, "pow": pow, "print": print,
    "range": range, "repr": repr, "reversed": reversed,
    "round": round, "set": set, "slice": slice, "sorted": sorted,
    "str": str, "sum": sum, "tuple": tuple, "type": type,
    "zip": zip,
}

# Safe math functions
_SAFE_MATH = {
    "ceil": math.ceil, "floor": math.floor, "sqrt": math.sqrt,
    "log": math.log, "log2": math.log2, "log10": math.log10,
    "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "pi": math.pi, "e": math.e, "inf": math.inf,
    "factorial": math.factorial, "gcd": math.gcd,
}

# Dangerous operations to block (math is allowed as a safe module)
_BLOCKED_PATTERNS = [
    r"__\w+__",  # Dunder methods
    r"import\s+",  # Import statements
    r"exec\s*\(",  # exec()
    r"eval\s*\(",  # nested eval
    r"open\s*\(",  # File operations
    r"\bos\.",  # OS module (with word boundary)
    r"\bsys\.",  # Sys module (with word boundary)
    r"subprocess",  # Subprocess
    r"shutil",  # Shell utilities
    r"pathlib",  # Path operations
    r"__import__",  # Dynamic import
    r"globals\s*\(",  # globals()
    r"locals\s*\(",  # locals()
    r"compile\s*\(",  # compile()
    r"getattr\s*\(",  # getattr (can access restricted attrs)
]


class CodeExecutionSkill(BaseSkill):
    """Executes Python expressions in a sandboxed environment."""

    def __init__(self) -> None:
        super().__init__(
            name="code_executor",
            description="执行Python代码表达式，支持数学计算、数据处理等",
        )

    async def execute(
        self,
        query: str,
        context: dict[str, Any] | None = None,
    ) -> SkillResult:
        """Execute a Python expression with safety checks."""
        code = self._extract_code(query)
        if not code:
            return SkillResult(
                success=False,
                error="未找到可执行的Python代码",
            )

        # Safety check
        safety_result = self._check_safety(code)
        if not safety_result["safe"]:
            return SkillResult(
                success=False,
                error=f"安全检查未通过: {safety_result['reason']}",
            )

        try:
            # Build restricted environment
            env = {"__builtins__": _SAFE_BUILTINS, "math": type("Math", (), _SAFE_MATH)()}

            # Execute with timeout
            result = self._execute_with_timeout(code, env, timeout=5)

            return SkillResult(
                success=True,
                result=str(result),
                metadata={"code": code, "execution_time_ms": 0},
            )
        except TimeoutError:
            return SkillResult(success=False, error="代码执行超时（5秒限制）")
        except Exception as e:
            return SkillResult(success=False, error=f"执行错误: {e}")

    def _extract_code(self, query: str) -> str:
        """Extract Python code from query."""
        # Try code block first
        code_match = re.search(r"```(?:python)?\s*\n?(.*?)```", query, re.DOTALL)
        if code_match:
            return code_match.group(1).strip()

        # Try inline code
        inline_match = re.search(r"`([^`]+)`", query)
        if inline_match:
            return inline_match.group(1).strip()

        # Try to detect if the whole query is code
        code_indicators = ["+", "-", "*", "/", "**", "//", "%", "(", ".", "="]
        if any(op in query for op in code_indicators):
            if not any(word in query.lower() for word in ["what", "how", "why", "please", "help"]):
                return query.strip()

        return ""

    def _check_safety(self, code: str) -> dict[str, Any]:
        """Check code for dangerous operations."""
        for pattern in _BLOCKED_PATTERNS:
            if re.search(pattern, code, re.IGNORECASE):
                return {"safe": False, "reason": f"检测到受限操作: {pattern}"}

        # AST-based check for additional safety
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    return {"safe": False, "reason": "不允许import语句"}
                if isinstance(node, ast.Attribute):
                    if node.attr.startswith("_"):
                        return {"safe": False, "reason": f"不允许访问私有属性: {node.attr}"}
        except SyntaxError as e:
            return {"safe": False, "reason": f"语法错误: {e}"}

        return {"safe": True, "reason": ""}

    def _execute_with_timeout(self, code: str, env: dict, timeout: int = 5) -> Any:
        """Execute code in a subprocess with real timeout protection."""
        import subprocess
        import sys

        # Build a minimal script that runs the code in a restricted env
        script = (
            "import math, json, sys\n"
            "_safe_builtins = {k: __builtins__[k] if isinstance(__builtins__, dict) "
            "else getattr(__builtins__, k) for k in "
            "'abs all any bool dict enumerate filter float format int len list map "
            "max min pow print range repr reversed round set slice sorted str sum tuple zip'.split() "
            "if (k in __builtins__ if isinstance(__builtins__, dict) else hasattr(__builtins__, k))}\n"
            "_safe_builtins['__import__'] = None\n"
            "_env = {'__builtins__': _safe_builtins, 'math': math}\n"
            f"_code = {code!r}\n"
            "try:\n"
            "    _r = eval(_code, _env)\n"
            "    if _r is not None: print(json.dumps({'ok': True, 'result': str(_r)}))\n"
            "    else: print(json.dumps({'ok': True, 'result': '执行完成（无返回值）'}))\n"
            "except SyntaxError:\n"
            "    _lo = {}\n"
            "    exec(_code, _env, _lo)\n"
            "    _v = list(_lo.values())[-1] if _lo else '执行完成（无返回值）'\n"
            "    print(json.dumps({'ok': True, 'result': str(_v)}))\n"
            "except Exception as _e:\n"
            "    print(json.dumps({'ok': False, 'error': str(_e)}))\n"
        )

        try:
            result = subprocess.run(
                [sys.executable, "-c", script],
                capture_output=True, text=True, timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            raise TimeoutError()

        if result.returncode != 0:
            stderr = result.stderr.strip()
            if "TimeoutError" in stderr:
                raise TimeoutError()
            raise RuntimeError(stderr or "执行失败")

        import json as _json
        try:
            output = _json.loads(result.stdout.strip().split("\n")[-1])
        except (ValueError, IndexError):
            return result.stdout.strip()

        if output.get("ok"):
            return output["result"]
        raise RuntimeError(output.get("error", "未知错误"))


# Module-level instance for auto-discovery
code_skill = CodeExecutionSkill()
