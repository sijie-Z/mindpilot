"""
Data analysis skill for CSV/JSON data processing.

Parses structured data, computes statistics, and generates summaries.

Auto-discovered by the skill registry.
"""
from __future__ import annotations

import csv
import io
import json
import re
import statistics
from typing import Any

from app.skills.base import BaseSkill, SkillResult


class DataAnalysisSkill(BaseSkill):
    """Analyzes structured data (CSV, JSON) and computes statistics."""

    def __init__(self) -> None:
        super().__init__(
            name="data_analysis",
            description="分析CSV/JSON数据，计算统计指标（均值、中位数、标准差等）",
        )

    async def execute(
        self,
        query: str,
        context: dict[str, Any] | None = None,
    ) -> SkillResult:
        """Analyze data based on query."""
        ctx = context or {}

        # Try to get data from context
        data = ctx.get("data")
        data_format = ctx.get("data_format", "auto")

        if data is None:
            # Try to extract data from query
            data, data_format = self._extract_data(query)

        if data is None:
            return SkillResult(
                success=False,
                error="未找到可分析的数据。请提供CSV或JSON格式的数据。",
            )

        try:
            if data_format == "csv" or (data_format == "auto" and self._looks_like_csv(data)):
                result = self._analyze_csv(data)
            elif data_format == "json" or (data_format == "auto" and self._looks_like_json(data)):
                result = self._analyze_json(data)
            elif isinstance(data, list):
                result = self._analyze_list(data)
            else:
                return SkillResult(
                    success=False,
                    error=f"不支持的数据格式: {type(data).__name__}",
                )

            return SkillResult(
                success=True,
                result=result["summary"],
                metadata=result["stats"],
            )
        except Exception as e:
            return SkillResult(success=False, error=f"数据分析错误: {e}")

    def _extract_data(self, query: str) -> tuple[Any, str]:
        """Extract data from query text."""
        # Try JSON array
        json_match = re.search(r"\[.*\]", query, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group())
                return data, "json"
            except json.JSONDecodeError:
                pass

        # Try CSV-like content
        csv_match = re.search(r"```(?:csv)?\s*\n?(.*?)```", query, re.DOTALL)
        if csv_match:
            return csv_match.group(1).strip(), "csv"

        # Try numbers
        numbers = re.findall(r"-?\d+\.?\d*", query)
        if len(numbers) >= 2:
            return [float(n) for n in numbers], "json"

        return None, "auto"

    def _looks_like_csv(self, data: str) -> bool:
        """Check if data looks like CSV."""
        lines = data.strip().split("\n")
        if len(lines) < 2:
            return False
        # Check if lines have consistent comma/tab separation
        first_line_commas = lines[0].count(",")
        return first_line_commas > 0

    def _looks_like_json(self, data: str) -> bool:
        """Check if data looks like JSON."""
        try:
            json.loads(data)
            return True
        except (json.JSONDecodeError, TypeError):
            return False

    def _analyze_csv(self, data: str) -> dict[str, Any]:
        """Analyze CSV data."""
        reader = csv.DictReader(io.StringIO(data))
        rows = list(reader)

        if not rows:
            return {"summary": "空数据集", "stats": {}}

        headers = reader.fieldnames or []
        numeric_cols = []

        # Identify numeric columns
        for header in headers:
            values = [row.get(header, "") for row in rows]
            try:
                [float(v) for v in values if v]
                numeric_cols.append(header)
            except ValueError:
                continue

        stats = {
            "row_count": len(rows),
            "column_count": len(headers),
            "columns": headers,
            "numeric_columns": numeric_cols,
            "column_stats": {},
        }

        # Compute stats for numeric columns
        for col in numeric_cols:
            values = [float(row.get(col, 0)) for row in rows if row.get(col)]
            if values:
                stats["column_stats"][col] = self._compute_stats(values)

        # Build summary
        summary_parts = [
            f"数据集: {len(rows)} 行 × {len(headers)} 列",
            f"数值列: {', '.join(numeric_cols) if numeric_cols else '无'}",
        ]
        for col, col_stats in stats["column_stats"].items():
            summary_parts.append(
                f"\n{col}: 均值={col_stats['mean']:.2f}, "
                f"中位数={col_stats['median']:.2f}, "
                f"标准差={col_stats['stdev']:.2f}, "
                f"范围=[{col_stats['min']:.2f}, {col_stats['max']:.2f}]"
            )

        return {"summary": "\n".join(summary_parts), "stats": stats}

    def _analyze_json(self, data: str | list | dict) -> dict[str, Any]:
        """Analyze JSON data."""
        if isinstance(data, (list, dict)):
            parsed = data
        else:
            parsed = json.loads(data)

        if isinstance(parsed, list):
            return self._analyze_list(parsed)
        elif isinstance(parsed, dict):
            return self._analyze_dict(parsed)
        else:
            return {"summary": f"JSON值: {parsed}", "stats": {"value": parsed}}

    def _analyze_list(self, data: list[Any]) -> dict[str, Any]:
        """Analyze a list of values."""
        if not data:
            return {"summary": "空列表", "stats": {}}

        # Try numeric analysis
        try:
            numbers = [float(x) for x in data]
            stats = self._compute_stats(numbers)
            summary = (
                f"数值列表: {len(numbers)} 个元素\n"
                f"均值={stats['mean']:.2f}, 中位数={stats['median']:.2f}, "
                f"标准差={stats['stdev']:.2f}\n"
                f"范围=[{stats['min']:.2f}, {stats['max']:.2f}]"
            )
            return {"summary": summary, "stats": {"list_stats": stats}}
        except (ValueError, TypeError):
            pass

        # Non-numeric list
        if isinstance(data[0], dict):
            return self._analyze_list_of_dicts(data)

        return {
            "summary": f"列表: {len(data)} 个元素 (类型: {type(data[0]).__name__})",
            "stats": {"count": len(data)},
        }

    def _analyze_list_of_dicts(self, data: list[dict]) -> dict[str, Any]:
        """Analyze a list of dictionaries (like JSON array of objects)."""
        if not data:
            return {"summary": "空数据集", "stats": {}}

        headers = list(data[0].keys())
        numeric_cols = []

        for header in headers:
            values = [item.get(header) for item in data if item.get(header) is not None]
            try:
                [float(v) for v in values]
                numeric_cols.append(header)
            except (ValueError, TypeError):
                continue

        stats = {
            "row_count": len(data),
            "column_count": len(headers),
            "columns": headers,
            "numeric_columns": numeric_cols,
            "column_stats": {},
        }

        for col in numeric_cols:
            values = [float(item.get(col, 0)) for item in data if item.get(col) is not None]
            if values:
                stats["column_stats"][col] = self._compute_stats(values)

        summary_parts = [f"数据集: {len(data)} 条记录, {len(headers)} 个字段"]
        for col, col_stats in stats["column_stats"].items():
            summary_parts.append(
                f"{col}: 均值={col_stats['mean']:.2f}, "
                f"中位数={col_stats['median']:.2f}, "
                f"标准差={col_stats['stdev']:.2f}"
            )

        return {"summary": "\n".join(summary_parts), "stats": stats}

    def _analyze_dict(self, data: dict) -> dict[str, Any]:
        """Analyze a dictionary."""
        summary_parts = [f"字典: {len(data)} 个键值对"]
        for key, value in data.items():
            if isinstance(value, (int, float)):
                summary_parts.append(f"  {key}: {value}")
            elif isinstance(value, list):
                summary_parts.append(f"  {key}: 列表 ({len(value)} 项)")
            elif isinstance(value, dict):
                summary_parts.append(f"  {key}: 字典 ({len(value)} 键)")
            else:
                summary_parts.append(f"  {key}: {str(value)[:50]}")

        return {"summary": "\n".join(summary_parts), "stats": {"keys": list(data.keys())}}

    def _compute_stats(self, values: list[float]) -> dict[str, float]:
        """Compute statistical summary for numeric values."""
        if not values:
            return {}

        sorted_vals = sorted(values)
        n = len(sorted_vals)

        result = {
            "count": n,
            "sum": sum(values),
            "mean": statistics.mean(values),
            "median": statistics.median(values),
            "min": min(values),
            "max": max(values),
            "range": max(values) - min(values),
        }

        if n >= 2:
            result["stdev"] = statistics.stdev(values)
            result["variance"] = statistics.variance(values)

        # Percentiles
        if n >= 4:
            q1_idx = n // 4
            q3_idx = (3 * n) // 4
            result["q1"] = sorted_vals[q1_idx]
            result["q3"] = sorted_vals[q3_idx]
            result["iqr"] = result["q3"] - result["q1"]

        return result


# Module-level instance for auto-discovery
analysis_skill = DataAnalysisSkill()
