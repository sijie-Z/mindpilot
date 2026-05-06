"""
Feishu (Lark) Bot webhook handler.
Integrates with MindPilot backend API for intelligent Q&A.
"""
import hashlib
import json

from fastapi import APIRouter, HTTPException, Request

from app.core.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


class FeishuConfig:
    """Feishu bot configuration."""
    APP_ID: str = ""
    APP_SECRET: str = ""
    VERIFICATION_TOKEN: str = ""
    ENCRYPT_KEY: str = ""
    MINDPILOT_API: str = "http://localhost:8002/api/chat/"
    BOT_NAME: str = "MindPilot"


feishu_config = FeishuConfig()


def verify_signature(timestamp: str, nonce: str, body: str, signature: str) -> bool:
    """Verify Feishu webhook signature."""
    if not feishu_config.ENCRYPT_KEY:
        return True  # Skip verification if no key configured

    content = f"{timestamp}{nonce}{feishu_config.ENCRYPT_KEY}{body}"
    expected = hashlib.sha256(content.encode()).hexdigest()
    return expected == signature


@router.post("/webhook")
async def feishu_webhook(request: Request):
    """
    Handle Feishu webhook events.
    Supports: url_verification, im.message.receive_v1
    """
    body = await request.body()
    body_str = body.decode("utf-8")
    headers = request.headers

    # Verify signature
    timestamp = headers.get("X-Lark-Signature-Timestamp", "")
    nonce = headers.get("X-Lark-Request-Nonce", "")
    signature = headers.get("X-Lark-Signature", "")

    if not verify_signature(timestamp, nonce, body_str, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")

    data = json.loads(body_str)

    # Handle URL verification challenge
    if data.get("type") == "url_verification":
        challenge = data.get("challenge", "")
        token = data.get("token", "")
        if token != feishu_config.VERIFICATION_TOKEN:
            raise HTTPException(status_code=401, detail="Invalid token")
        return {"challenge": challenge}

    # Handle message events
    event_type = data.get("header", {}).get("event_type", "") or data.get("event", {}).get("type", "")

    if event_type == "im.message.receive_v1":
        return await handle_message(data)

    return {"status": "ok"}


async def handle_message(data: dict) -> dict:
    """Process incoming message from Feishu."""
    try:
        event = data.get("event", {})
        message = event.get("message", {})
        sender = event.get("sender", {})

        # Extract message content
        msg_type = message.get("message_type", "text")
        content_str = message.get("content", "{}")
        content = json.loads(content_str) if isinstance(content_str, str) else content_str

        # Get text from message
        query = ""
        if msg_type == "text":
            query = content.get("text", "").strip()
        elif msg_type == "post":
            # Rich text - extract plain text
            posts = content.get("content", [])
            for post in posts:
                for element in post:
                    if element.get("tag") == "text":
                        query += element.get("text", "")
        elif msg_type == "image":
            query = "[用户发送了一张图片]"
        else:
            query = f"[不支持的消息类型: {msg_type}]"

        if not query:
            return {"status": "ok"}

        # Remove @bot mention
        query = query.replace("@_user_1", "").strip()

        # Call MindPilot backend
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.post(
                feishu_config.MINDPILOT_API,
                json={
                    "query": query,
                    "user_id": sender.get("sender_id", {}).get("user_id", "feishu_user"),
                },
                timeout=60.0,
            )
            result = response.json()

        answer = result.get("answer", "抱歉，我暂时无法回答这个问题。")

        # Reply to Feishu
        chat_id = message.get("chat_id", "")
        msg_id = message.get("message_id", "")

        if chat_id:
            await reply_message(chat_id, answer, msg_id)

        return {"status": "ok"}

    except Exception as e:
        logger.error("Feishu message handling error", error=str(e))
        return {"status": "error", "message": str(e)}


async def reply_message(
    chat_id: str,
    text: str,
    reply_to: str = "",
) -> dict:
    """Send a reply message via Feishu API."""
    try:
        token = await get_feishu_token()
        if not token:
            logger.warning("Failed to get Feishu token")
            return {}

        import httpx
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        payload = {
            "receive_id": chat_id,
            "msg_type": "text",
            "content": json.dumps({"text": text}),
        }

        if reply_to:
            payload["reply_to"] = reply_to

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://open.feishu.cn/open-apis/im/v1/messages",
                headers=headers,
                json=payload,
                params={"receive_id_type": "chat_id"},
                timeout=30.0,
            )
            return response.json()

    except Exception as e:
        logger.error("Feishu reply error", error=str(e))
        return {}


async def get_feishu_token() -> str:
    """Get Feishu tenant access token."""
    if not feishu_config.APP_ID:
        return ""

    try:
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                json={
                    "app_id": feishu_config.APP_ID,
                    "app_secret": feishu_config.APP_SECRET,
                },
                timeout=10.0,
            )
            data = response.json()
            return data.get("tenant_access_token", "")
    except Exception as e:
        logger.error("Feishu token error", error=str(e))
        return ""


@router.get("/config")
async def get_feishu_config():
    """Get Feishu bot configuration status."""
    return {
        "configured": bool(feishu_config.APP_ID),
        "bot_name": feishu_config.BOT_NAME,
        "api_endpoint": feishu_config.MINDPILOT_API,
    }
