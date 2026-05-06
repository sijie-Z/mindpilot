"""
Calculator skill for mathematical computations.
"""
import ast
import operator

from app.skills.base import BaseSkill, SkillResult


class CalcSkill(BaseSkill):
    """Skill for mathematical calculations."""

    # Allowed operators for safe evaluation
    OPERATORS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
        ast.Mod: operator.mod,
        ast.USub: operator.neg,
    }

    def __init__(self):
        super().__init__(
            name="calculator",
            description="Perform mathematical calculations"
        )

    async def execute(
        self,
        query: str,
        context: dict = None,
    ) -> SkillResult:
        """
        Safely evaluate mathematical expressions.
        Uses AST parsing to prevent code injection.
        """
        try:
            # Extract expression from query
            expr = self._extract_expression(query)

            if not expr:
                return SkillResult(
                    success=True,
                    result="请提供一个数学表达式，例如：计算 2+2 或 15*8",
                )

            # Safe evaluation
            result = self._safe_eval(expr)

            return SkillResult(
                success=True,
                result=f"计算结果：{expr} = {result}",
                metadata={
                    "expression": expr,
                    "result": result,
                }
            )

        except Exception as e:
            return SkillResult(
                success=False,
                error=f"计算错误：{str(e)}",
            )

    def _extract_expression(self, query: str) -> str:
        """Extract mathematical expression from query."""
        # Remove common prefixes
        prefixes = ["计算", "算一下", "等于多少", "是多少", "帮我算", "求"]
        expr = query
        for prefix in prefixes:
            if prefix in expr:
                expr = expr.replace(prefix, "")

        # Keep only math-related characters
        import re
        expr = re.sub(r"[^0-9+\-*/().^%\s]", "", expr).strip()

        return expr if expr else ""

    def _safe_eval(self, expr: str) -> float:
        """Safely evaluate expression using AST."""
        node = ast.parse(expr, mode="eval")
        return self._eval_node(node.body)

    def _eval_node(self, node):
        """Recursively evaluate AST node."""
        if isinstance(node, ast.Num):
            return node.n
        elif isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.BinOp):
            left = self._eval_node(node.left)
            right = self._eval_node(node.right)
            op_type = type(node.op)
            if op_type in self.OPERATORS:
                return self.OPERATORS[op_type](left, right)
            else:
                raise ValueError(f"Unsupported operator: {op_type}")
        elif isinstance(node, ast.UnaryOp):
            operand = self._eval_node(node.operand)
            op_type = type(node.op)
            if op_type in self.OPERATORS:
                return self.OPERATORS[op_type](operand)
            else:
                raise ValueError(f"Unsupported operator: {op_type}")
        else:
            raise ValueError(f"Unsupported node type: {type(node)}")


# Global instance
calc_skill = CalcSkill()
