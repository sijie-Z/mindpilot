"""
MCP (Model Context Protocol) implementation for tool calling.
Enables LLM to invoke external tools like search, calculator, etc.
"""
import asyncio
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel


class MCPTool(BaseModel):
    """Definition of an MCP tool."""
    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any] | None = None


class MCPToolResult(BaseModel):
    """Result of a tool execution."""
    tool: str
    success: bool
    result: Any | None = None
    error: str | None = None
    latency_ms: int = 0


class MCPServer:
    """
    MCP Server for managing tool registrations and executions.

    Tools are registered with name, description, and input schema.
    LLM can call tools via JSON-RPC style messages.
    """

    def __init__(self):
        self._tools: dict[str, Callable] = {}
        self._tool_schemas: dict[str, dict] = {}

    def register(
        self,
        name: str,
        description: str,
        handler: Callable,
        input_schema: dict[str, Any] = None,
    ):
        """
        Register a tool with the MCP server.

        Args:
            name: Tool name (e.g., "search", "calculator")
            description: Human-readable description
            handler: Async function to execute the tool
            input_schema: JSON Schema for tool inputs
        """
        self._tools[name] = handler
        self._tool_schemas[name] = {
            "name": name,
            "description": description,
            "input_schema": input_schema or {"type": "object"},
        }

    def list_tools(self) -> list[dict[str, str]]:
        """List all registered tools."""
        return [
            {"name": name, "description": schema["description"]}
            for name, schema in self._tool_schemas.items()
        ]

    def get_tool_schemas(self) -> list[dict]:
        """Get tool schemas for LLM function calling."""
        return list(self._tool_schemas.values())

    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> MCPToolResult:
        """
        Execute a registered tool with the given arguments.

        Args:
            tool_name: Name of the tool to execute
            arguments: Input arguments matching the tool's input schema

        Returns:
            MCPToolResult with execution outcome
        """
        import time
        start = time.time()

        if tool_name not in self._tools:
            return MCPToolResult(
                tool=tool_name,
                success=False,
                error=f"Tool '{tool_name}' not found. Available: {list(self._tools.keys())}",
                latency_ms=int((time.time() - start) * 1000),
            )

        try:
            handler = self._tools[tool_name]

            # Execute handler (may be sync or async)
            if asyncio.iscoroutinefunction(handler):
                result = await handler(**arguments)
            else:
                result = handler(**arguments)

            return MCPToolResult(
                tool=tool_name,
                success=True,
                result=result,
                latency_ms=int((time.time() - start) * 1000),
            )

        except Exception as e:
            return MCPToolResult(
                tool=tool_name,
                success=False,
                error=str(e),
                latency_ms=int((time.time() - start) * 1000),
            )

    async def execute_batch(
        self, calls: list[dict[str, Any]]
    ) -> list[MCPToolResult]:
        """Execute multiple tools in parallel."""
        tasks = []
        for call in calls:
            tool_name = call.get("name")
            arguments = call.get("arguments", {})
            tasks.append(self.execute(tool_name, arguments))

        return await asyncio.gather(*tasks)


def build_mcp_tools_prompt(tools: list[dict]) -> str:
    """
    Build a system prompt section describing available MCP tools.
    Used for LLM function calling.
    """
    if not tools:
        return ""

    lines = ["You have access to the following tools:"]
    lines.append("")

    for tool in tools:
        lines.append(f"### {tool['name']}")
        lines.append(f"Description: {tool['description']}")
        schema = tool.get("input_schema", {})
        props = schema.get("properties", {})
        if props:
            lines.append("Arguments:")
            for param_name, param_info in props.items():
                param_type = param_info.get("type", "any")
                param_desc = param_info.get("description", "")
                lines.append(f"  - {param_name} ({param_type}): {param_desc}")
        lines.append("")

    return "\n".join(lines)


# Global MCP server instance
mcp_server = MCPServer()


# Register built-in tools
async def register_builtin_tools():
    """Register MindPilot's built-in MCP tools."""
    from app.skills.calc_skill import calc_skill
    from app.skills.image_skill import image_skill
    from app.skills.rag_skill import rag_skill
    from app.skills.search_skill import search_skill

    # Calculator tool
    mcp_server.register(
        name="calculator",
        description="Perform mathematical calculations. Input a math expression as a string.",
        handler=lambda expression: asyncio.run(calc_skill.execute(expression)),
        input_schema={
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Mathematical expression to evaluate, e.g., '2 + 3 * 4'",
                }
            },
            "required": ["expression"],
        },
    )

    # Web search tool
    mcp_server.register(
        name="web_search",
        description="Search the web for real-time information using Jina AI.",
        handler=lambda query: asyncio.run(search_skill.execute(query)),
        input_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query for web search",
                }
            },
            "required": ["query"],
        },
    )

    # RAG tool
    mcp_server.register(
        name="rag_query",
        description="Query the knowledge base for relevant documents.",
        handler=lambda query, knowledge_id: asyncio.run(rag_skill.execute(query, {"knowledge_id": knowledge_id})),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "knowledge_id": {"type": "string", "description": "Knowledge base ID (optional)"},
            },
            "required": ["query"],
        },
    )

    # Image understanding tool
    mcp_server.register(
        name="image_understand",
        description="Understand and answer questions about an image using VLM.",
        handler=lambda image_path, question: asyncio.run(image_skill.execute(question, {"image_path": image_path})),
        input_schema={
            "type": "object",
            "properties": {
                "image_path": {"type": "string", "description": "Path to the image file"},
                "question": {"type": "string", "description": "Question about the image"},
            },
            "required": ["image_path", "question"],
        },
    )


# Lazy initialization
_tools_registered = False


async def ensure_tools_registered():
    """Register tools once on first use."""
    global _tools_registered
    if not _tools_registered:
        await register_builtin_tools()
        _tools_registered = True
