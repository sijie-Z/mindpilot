"""
MindPilot Admin Plugin for NoneBot2.
Provides admin commands for managing the bot and knowledge bases.
"""
import os
import httpx
from nonebot import on_command, get_driver, permission
from nonebot.rule import command
from nonebot.adapters.onebot.v11 import (
    Bot,
    Event,
    MessageEvent,
    GroupMessageEvent,
    PrivateMessageEvent,
    Message,
)
from nonebot.params import CommandArg
from nonebot.log import logger
from typing import Optional

# Backend API URL
API_BASE = os.getenv("API_BASE_URL", "http://127.0.0.1:8002")

# Admin users (QQ IDs)
ADMIN_USERS = os.getenv("ADMIN_USERS", "").split(",")
ADMIN_USERS = [u.strip() for u in ADMIN_USERS if u.strip()]

# Super users from NoneBot config
SUPERUSERS = get_driver().config.superusers


def is_admin(event: MessageEvent) -> bool:
    """Check if user is admin."""
    user_id = str(event.user_id)
    return user_id in ADMIN_USERS or user_id in SUPERUSERS


# Command: /admin stats - Show system statistics
admin_stats = on_command("admin stats", aliases={"管理统计", "系统统计"}, priority=5, block=True)


@admin_stats.handle()
async def handle_admin_stats(bot: Bot, event: MessageEvent):
    """Show system statistics (admin only)."""
    if not is_admin(event):
        await admin_stats.finish("❌ 权限不足，此命令仅限管理员使用")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{API_BASE}/api/admin/stats",
                headers={"X-API-Key": os.getenv("API_KEY", "")}
            )
            if response.status_code == 200:
                data = response.json()

                msg = "📊 MindPilot 系统统计\n\n"
                msg += f"👤 用户数: {data.get('users', 0)}\n"
                msg += f"📚 知识库: {data.get('knowledge_bases', 0)}\n"
                msg += f"📄 文档数: {data.get('documents', 0)}\n"
                msg += f"📝 文档片段: {data.get('chunks', 0)}\n"
                msg += f"💬 会话数: {data.get('sessions', 0)}\n"
                msg += f"💭 消息数: {data.get('messages', 0)}\n"
                msg += f"📈 评估记录: {data.get('evaluations', 0)}\n"

                await admin_stats.finish(msg)
            else:
                await admin_stats.finish(f"⚠️ 获取统计失败: {response.status_code}")

    except Exception as e:
        logger.error(f"Admin stats error: {e}")
        await admin_stats.finish("❌ 获取统计失败")


# Command: /admin health - Check system health
admin_health = on_command("admin health", aliases={"管理健康检查"}, priority=5, block=True)


@admin_health.handle()
async def handle_admin_health(bot: Bot, event: MessageEvent):
    """Check system health (admin only)."""
    if not is_admin(event):
        await admin_health.finish("❌ 权限不足")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{API_BASE}/api/admin/health")
            if response.status_code == 200:
                data = response.json()
                checks = data.get("checks", {})

                status_emoji = {"ok": "✅", "error": "❌", "disconnected": "⚠️"}

                msg = f"🏥 系统健康检查\n"
                msg += f"状态: {data.get('status', 'unknown')}\n\n"
                msg += "组件状态:\n"

                for name, status in checks.items():
                    emoji = status_emoji.get(status, "❓")
                    msg += f"{emoji} {name}: {status}\n"

                await admin_health.finish(msg)
            else:
                await admin_health.finish("⚠️ 健康检查失败")

    except Exception as e:
        logger.error(f"Health check error: {e}")
        await admin_health.finish("❌ 无法连接后端")


# Command: /admin kb - Knowledge base management
admin_kb = on_command("admin kb", aliases={"管理知识库"}, priority=5, block=True)


@admin_kb.handle()
async def handle_admin_kb(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    """Manage knowledge bases (admin only)."""
    if not is_admin(event):
        await admin_kb.finish("❌ 权限不足")

    arg_text = args.extract_plain_text().strip()

    if not arg_text:
        # List all knowledge bases with details
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{API_BASE}/api/knowledge/")
                if response.status_code == 200:
                    kbs = response.json().get("knowledges", response.json())

                    msg = "📚 知识库管理\n\n"
                    for kb in kbs:
                        kb_id = kb.get("id", "")
                        name = kb.get("name", "未知")
                        doc_count = kb.get("doc_count", 0)
                        chunk_count = kb.get("chunk_count", 0)
                        is_public = kb.get("is_public", False)

                        msg += f"📦 {name}\n"
                        msg += f"   ID: {kb_id}\n"
                        msg += f"   文档: {doc_count} | 片段: {chunk_count}\n"
                        msg += f"   公开: {'是' if is_public else '否'}\n\n"

                    msg += "命令:\n"
                    msg += "/admin kb create <名称> - 创建知识库\n"
                    msg += "/admin kb delete <ID> - 删除知识库"

                    await admin_kb.finish(msg)
        except Exception as e:
            logger.error(f"KB list error: {e}")
            await admin_kb.finish("❌ 获取知识库列表失败")

    # Parse command
    parts = arg_text.split(maxsplit=1)
    action = parts[0].lower()

    if action == "create":
        if len(parts) < 2:
            await admin_kb.finish("请提供知识库名称: /admin kb create <名称>")

        name = parts[1]
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{API_BASE}/api/knowledge/",
                    json={"name": name, "description": f"由QQ管理员创建"}
                )
                if response.status_code == 200:
                    data = response.json()
                    await admin_kb.finish(f"✅ 知识库创建成功\nID: {data.get('id', '')}\n名称: {name}")
                else:
                    await admin_kb.finish(f"❌ 创建失败: {response.status_code}")
        except Exception as e:
            logger.error(f"KB create error: {e}")
            await admin_kb.finish("❌ 创建知识库失败")

    elif action == "delete":
        if len(parts) < 2:
            await admin_kb.finish("请提供知识库ID: /admin kb delete <ID>")

        kb_id = parts[1]
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.delete(f"{API_BASE}/api/knowledge/{kb_id}")
                if response.status_code == 200:
                    await admin_kb.finish(f"✅ 知识库已删除: {kb_id}")
                elif response.status_code == 404:
                    await admin_kb.finish(f"❌ 知识库不存在: {kb_id}")
                else:
                    await admin_kb.finish(f"❌ 删除失败: {response.status_code}")
        except Exception as e:
            logger.error(f"KB delete error: {e}")
            await admin_kb.finish("❌ 删除知识库失败")

    else:
        await admin_kb.finish(f"未知操作: {action}\n可用: create, delete")


# Command: /admin eval - Show evaluation summary
admin_eval = on_command("admin eval", aliases={"管理评估"}, priority=5, block=True)


@admin_eval.handle()
async def handle_admin_eval(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    """Show evaluation summary (admin only)."""
    if not is_admin(event):
        await admin_eval.finish("❌ 权限不足")

    arg_text = args.extract_plain_text().strip()
    days = 7

    if arg_text:
        try:
            days = int(arg_text)
            if days < 1 or days > 30:
                await admin_eval.finish("天数范围: 1-30")
        except ValueError:
            await admin_eval.finish("请输入有效天数，例如: /admin eval 7")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{API_BASE}/api/admin/evaluations/summary",
                params={"days": days}
            )
            if response.status_code == 200:
                data = response.json()

                msg = f"📈 RAG评估统计 (最近{days}天)\n\n"
                msg += f"总评估数: {data.get('total_evaluations', 0)}\n"
                msg += f"平均忠实度: {data.get('avg_faithfulness', 0):.3f}\n"
                msg += f"平均相关性: {data.get('avg_answer_relevance', 0):.3f}\n"
                msg += f"平均上下文精度: {data.get('avg_context_precision', 0):.3f}\n"
                msg += f"平均延迟: {data.get('avg_latency_ms', 0):.0f}ms\n"
                msg += f"总Token消耗: {data.get('total_tokens', 0)}\n"

                await admin_eval.finish(msg)
            else:
                await admin_eval.finish("⚠️ 获取评估数据失败")

    except Exception as e:
        logger.error(f"Eval summary error: {e}")
        await admin_eval.finish("❌ 获取评估数据失败")


# Command: /admin config - Show/modify config
admin_config = on_command("admin config", aliases={"管理配置"}, priority=5, block=True)


@admin_config.handle()
async def handle_admin_config(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    """Show or modify system config (admin only)."""
    if not is_admin(event):
        await admin_config.finish("❌ 权限不足")

    arg_text = args.extract_plain_text().strip()

    if not arg_text:
        # Show current config
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{API_BASE}/api/admin/config")
                if response.status_code == 200:
                    data = response.json()

                    msg = "⚙️ 系统配置\n\n"
                    msg += f"应用名称: {data.get('app_name', '')}\n"
                    msg += f"版本: {data.get('version', '')}\n"
                    msg += f"环境: {data.get('environment', '')}\n"
                    msg += f"调试模式: {data.get('debug', False)}\n"
                    msg += f"嵌入模型: {data.get('embedding_model', '')}\n"
                    msg += f"LLM模型: {data.get('llm_model', '')}\n"
                    msg += f"向量存储: {data.get('vector_store', '')}\n"
                    msg += f"切片大小: {data.get('chunk_size', 0)}\n"

                    await admin_config.finish(msg)
        except Exception as e:
            logger.error(f"Config error: {e}")
            await admin_config.finish("❌ 获取配置失败")

    # Parse modification command
    parts = arg_text.split(maxsplit=1)
    key = parts[0]
    value = parts[1] if len(parts) > 1 else None

    if not value:
        await admin_config.finish(f"请提供值: /admin config {key} <value>")

    # Note: Actual config modification requires backend support
    await admin_config.finish(f"⚠️ 配置修改需要后端支持，当前仅显示配置")


# Command: /admin users - User management
admin_users = on_command("admin users", aliases={"管理用户"}, priority=5, block=True)


@admin_users.handle()
async def handle_admin_users(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    """List users (admin only)."""
    if not is_admin(event):
        await admin_users.finish("❌ 权限不足")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{API_BASE}/api/admin/users",
                params={"limit": 10}
            )
            if response.status_code == 200:
                users = response.json()

                msg = "👤 用户列表\n\n"
                for u in users:
                    msg += f"• {u.get('username', '未知')}\n"
                    msg += f"  ID: {u.get('id', '')}\n"
                    msg += f"  角色: {u.get('role', 'user')}\n"
                    msg += f"  活跃: {'是' if u.get('is_active', True) else '否'}\n\n"

                await admin_users.finish(msg)
            else:
                await admin_users.finish("⚠️ 获取用户列表失败")

    except Exception as e:
        logger.error(f"Users list error: {e}")
        await admin_users.finish("❌ 获取用户列表失败")


# Command: /admin reload - Reload retriever
admin_reload = on_command("admin reload", aliases={"管理重载"}, priority=5, block=True)


@admin_reload.handle()
async def handle_admin_reload(bot: Bot, event: MessageEvent):
    """Reload retriever and clear caches (admin only)."""
    if not is_admin(event):
        await admin_reload.finish("❌ 权限不足")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Call backend reload endpoint if available
            response = await client.post(f"{API_BASE}/api/admin/reload")
            if response.status_code == 200:
                await admin_reload.finish("✅ 系统已重新加载")
            else:
                await admin_reload.finish("⚠️ 重载请求发送，但后端可能不支持此功能")

    except Exception as e:
        logger.error(f"Reload error: {e}")
        await admin_reload.finish("❌ 重载失败")


# Command: /admin broadcast - Broadcast message to groups
admin_broadcast = on_command("admin broadcast", aliases={"管理广播"}, priority=5, block=True)


@admin_broadcast.handle()
async def handle_admin_broadcast(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    """Broadcast message to all groups (admin only)."""
    if not is_admin(event):
        await admin_broadcast.finish("❌ 权限不足")

    message = args.extract_plain_text().strip()
    if not message:
        await admin_broadcast.finish("请提供广播内容: /admin broadcast <消息>")

    # Get all groups
    try:
        groups = await bot.get_group_list()

        success_count = 0
        for group in groups:
            group_id = group.get("group_id")
            try:
                await bot.send_group_msg(group_id=group_id, message=message)
                success_count += 1
            except Exception as e:
                logger.warning(f"Failed to send to group {group_id}: {e}")

        await admin_broadcast.finish(f"✅ 广播完成\n发送成功: {success_count}/{len(groups)} 个群")

    except Exception as e:
        logger.error(f"Broadcast error: {e}")
        await admin_broadcast.finish("❌ 广播失败")


# Command: /admin help - Admin help
admin_help = on_command("admin help", aliases={"管理帮助"}, priority=5, block=True)


@admin_help.handle()
async def handle_admin_help(bot: Bot, event: MessageEvent):
    """Show admin commands help."""
    if not is_admin(event):
        await admin_help.finish("❌ 权限不足")

    help_text = """🔧 MindPilot 管理命令

📊 统计与健康:
• /admin stats - 系统统计
• /admin health - 健康检查
• /admin eval [天数] - RAG评估统计

📚 知识库管理:
• /admin kb - 列出知识库
• /admin kb create <名称> - 创建知识库
• /admin kb delete <ID> - 删除知识库

👤 用户管理:
• /admin users - 用户列表

⚙️ 配置:
• /admin config - 显示配置

🔧 其他:
• /admin reload - 重载系统
• /admin broadcast <消息> - 群广播

💡 提示: 所有管理命令需要管理员权限"""

    await admin_help.finish(help_text)