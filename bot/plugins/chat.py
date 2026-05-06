"""
MindPilot Chat Plugin for NoneBot2.
Handles group and private messages, forwards to MindPilot backend.
"""
"""
MindPilot Chat Plugin for NoneBot2.
Thin client: all intelligence is in the MindPilot backend.
"""
import os
import httpx
from nonebot import on_message, on_command, get_driver
from nonebot.rule import to_me
from nonebot.adapters.onebot.v11 import (
    Bot,
    Event,
    MessageEvent,
    GroupMessageEvent,
    PrivateMessageEvent,
    Message,
    MessageSegment,
)
from nonebot.params import CommandArg
from nonebot.log import logger
from typing import Optional, Dict

API_BASE = os.getenv("API_BASE_URL", "http://127.0.0.1:8002")
DEFAULT_KB = os.getenv("DEFAULT_KNOWLEDGE_BASE", "")

# Session tracking: user_id -> {session_id, knowledge_base}
user_sessions: Dict[str, Dict] = {}

# Knowledge base cache
knowledge_bases: list = []


async def get_knowledge_bases() -> list:
    """Fetch available knowledge bases."""
    global knowledge_bases
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{API_BASE}/api/knowledge/")
            if response.status_code == 200:
                knowledge_bases = response.json().get("knowledges", response.json())
                return knowledge_bases
    except Exception as e:
        logger.error(f"Failed to fetch knowledge bases: {e}")
    return []


async def call_mindpilot_api(
    query: str,
    user_id: str,
    knowledge_base_id: Optional[str] = None
) -> dict:
    """Call MindPilot backend API."""
    session_data = user_sessions.get(user_id, {})
    session_id = session_data.get("session_id", "")
    kb_id = knowledge_base_id or session_data.get("knowledge_base", DEFAULT_KB)

    async with httpx.AsyncClient(timeout=120.0) as client:
        payload = {
            "query": query,
            "session_id": session_id,
            "user_id": user_id,
        }
        if kb_id:
            payload["knowledge_id"] = kb_id

        response = await client.post(f"{API_BASE}/api/chat/", json=payload)
        response.raise_for_status()
        return response.json()


def format_reply(answer: str, sources: list, evaluation: dict) -> str:
    """Format the reply message."""
    reply = answer

    # Add sources if available
    if sources:
        reply += "\n\n📚 参考来源："
        for i, source in enumerate(sources[:3], 1):
            filename = source.get("filename", "未知文档")
            score = source.get("score", 0)
            score_str = f" (相关度: {score:.0%})" if score else ""
            reply += f"\n[{i}] {filename}{score_str}"

    return reply


# Handler for @bot messages and private messages
chat_handler = on_message(rule=to_me(), priority=10, block=True)


@chat_handler.handle()
async def handle_chat(bot: Bot, event: MessageEvent):
    """Handle chat messages when bot is mentioned or in private chat."""
    # Extract text from message
    text = event.get_plaintext().strip()

    if not text:
        await chat_handler.finish("你好！我是 MindPilot，有什么可以帮你的？发送 /help 查看使用说明。")

    user_id = str(event.user_id)

    try:
        data = await call_mindpilot_api(text, user_id)

        answer = data.get("answer", "抱歉，没有找到答案。")
        sources = data.get("sources", [])
        evaluation = data.get("evaluation", {})

        # Update session
        new_session_id = data.get("session_id", "")
        if user_id not in user_sessions:
            user_sessions[user_id] = {}
        user_sessions[user_id]["session_id"] = new_session_id

        reply = format_reply(answer, sources, evaluation)
        await chat_handler.finish(reply)

    except httpx.TimeoutException:
        await chat_handler.finish("⏳ 请求超时，请稍后重试。")
    except httpx.HTTPStatusError as e:
        logger.error(f"API error: {e}")
        await chat_handler.finish("⚠️ 服务暂时不可用，请稍后重试。")
    except Exception as e:
        logger.error(f"Chat error: {e}")
        await chat_handler.finish("❌ 发生错误，请稍后重试。")


# Command: /kb - Switch knowledge base
kb_handler = on_command("kb", aliases={"知识库"}, priority=5, block=True)


@kb_handler.handle()
async def handle_kb(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    """Switch or list knowledge bases."""
    user_id = str(event.user_id)
    arg_text = args.extract_plain_text().strip()

    # Fetch knowledge bases
    kbs = await get_knowledge_bases()

    if not arg_text:
        # List available knowledge bases
        if not kbs:
            await kb_handler.finish("📭 暂无可用知识库，请先创建知识库。")

        current_kb = user_sessions.get(user_id, {}).get("knowledge_base", DEFAULT_KB)
        msg = "📚 可用知识库：\n\n"
        for i, kb in enumerate(kbs, 1):
            name = kb.get("name", kb.get("id", "未知"))
            kb_id = kb.get("id", "")
            doc_count = kb.get("doc_count", kb.get("document_count", 0))
            marker = " ✓" if kb_id == current_kb else ""
            msg += f"{i}. {name} ({doc_count} 文档){marker}\n"

        msg += "\n使用 /kb <名称或序号> 切换知识库"
        msg += "\n使用 /kb none 取消知识库绑定"
        await kb_handler.finish(msg)

    # Switch knowledge base
    if arg_text.lower() == "none" or arg_text.lower() == "无":
        if user_id in user_sessions:
            user_sessions[user_id]["knowledge_base"] = ""
        await kb_handler.finish("✅ 已取消知识库绑定，将使用通用对话模式。")

    # Find knowledge base by name or index
    try:
        index = int(arg_text) - 1
        if 0 <= index < len(kbs):
            kb = kbs[index]
        else:
            await kb_handler.finish("❌ 无效的序号，请重新输入。")
    except ValueError:
        # Search by name
        kb = next((k for k in kbs if arg_text.lower() in k.get("name", "").lower()), None)
        if not kb:
            await kb_handler.finish(f"❌ 未找到知识库: {arg_text}")

    kb_id = kb.get("id", "")
    kb_name = kb.get("name", "")

    if user_id not in user_sessions:
        user_sessions[user_id] = {}
    user_sessions[user_id]["knowledge_base"] = kb_id
    # Clear session when switching KB
    user_sessions[user_id]["session_id"] = ""

    await kb_handler.finish(f"✅ 已切换到知识库: {kb_name}")


# Command: /clear - Clear session
clear_handler = on_command("clear", aliases={"清除", "重置", "新对话"}, priority=5, block=True)


@clear_handler.handle()
async def handle_clear(bot: Bot, event: MessageEvent):
    """Clear user session."""
    user_id = str(event.user_id)
    if user_id in user_sessions:
        user_sessions[user_id]["session_id"] = ""
    await clear_handler.finish("✅ 会话已清除，开始新的对话。")


# Command: /help - Show help
help_handler = on_command("help", aliases={"帮助", "帮助信息"}, priority=5, block=True)


@help_handler.handle()
async def handle_help(bot: Bot, event: MessageEvent):
    """Show help message."""
    help_text = """🤖 MindPilot - 智能知识检索助手

📝 使用方法：
• @我 + 问题：我会回答你的问题
• 私聊直接发送问题

📚 知识库命令：
• /kb - 查看和切换知识库
• /kb <名称> - 切换到指定知识库
• /kb none - 使用通用对话模式

🔧 其他命令：
• /clear - 清除对话，开始新会话
• /status - 查看系统状态
• /help - 显示此帮助信息

✨ 支持功能：
📚 RAG知识库问答（上传文档后可用）
🔍 网络搜索
🔢 数学计算
🖼️ 图片理解

💡 提示：
• 绑定知识库后，回答将基于知识库内容
• 使用 /kb 命令管理知识库绑定"""

    await help_handler.finish(help_text)


# Command: /status - Check system status
status_handler = on_command("status", aliases={"状态", "系统状态"}, priority=5, block=True)


@status_handler.handle()
async def handle_status(bot: Bot, event: MessageEvent):
    """Check system status."""
    user_id = str(event.user_id)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{API_BASE}/health/detailed")
            if response.status_code == 200:
                data = response.json()
                components = data.get("components", {})

                # Build status message
                status_emoji = {"healthy": "✅", "unhealthy": "❌", "degraded": "⚠️"}

                msg = f"🤖 MindPilot 系统状态\n"
                msg += f"版本: {data.get('version', 'unknown')}\n"
                msg += f"运行时间: {data.get('uptime_seconds', 0):.0f}秒\n\n"
                msg += "组件状态：\n"

                for name, info in components.items():
                    emoji = status_emoji.get(info.get("status"), "❓")
                    latency = info.get("latency_ms", "")
                    latency_str = f" ({latency:.0f}ms)" if latency else ""
                    msg += f"{emoji} {name}{latency_str}\n"

                # User's current settings
                session_data = user_sessions.get(user_id, {})
                current_kb = session_data.get("knowledge_base", "无")
                msg += f"\n📚 当前知识库: {current_kb if current_kb else '通用模式'}"

                await status_handler.finish(msg)
            else:
                await status_handler.finish("⚠️ 后端服务异常")
    except Exception as e:
        logger.error(f"Status check error: {e}")
        await status_handler.finish("❌ 无法连接到后端服务")


# Command: /search - Force web search
search_handler = on_command("search", aliases={"搜索", "网搜"}, priority=5, block=True)


@search_handler.handle()
async def handle_search(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    """Force web search."""
    query = args.extract_plain_text().strip()

    if not query:
        await search_handler.finish("请输入搜索内容，例如: /search 人工智能发展现状")

    user_id = str(event.user_id)

    try:
        # Call with web search hint
        data = await call_mindpilot_api(f"[网络搜索] {query}", user_id)
        answer = data.get("answer", "抱歉，搜索失败。")
        await search_handler.finish(f"🔍 搜索结果：\n\n{answer}")
    except Exception as e:
        logger.error(f"Search error: {e}")
        await search_handler.finish("❌ 搜索失败，请稍后重试")


# Handle group message without @ for active groups
# This is optional and can be enabled per group
group_chat_handler = on_message(priority=99, block=False)


@group_chat_handler.handle()
async def handle_group_chat(bot: Bot, event: GroupMessageEvent):
    """
    Optional: Handle group messages without @.
    Enable this only for specific groups where bot should be more active.
    """
    # Check if group is in active list (configurable)
    # For now, this is disabled by default
    pass