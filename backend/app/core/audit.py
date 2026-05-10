"""
Audit logging utility for tracking user actions.
"""
from app.core.logger import get_logger
from app.storage.database import get_db_session
from sqlalchemy import text

logger = get_logger(__name__)


async def log_action(
    user_id: str | None = None,
    username: str | None = None,
    action: str = "",
    resource_type: str | None = None,
    resource_id: str | None = None,
    detail: str | None = None,
    ip_address: str | None = None,
):
    """Log a user action to the audit trail."""
    try:
        async with get_db_session() as db:
            await db.execute(
                text(
                    "INSERT INTO audit_logs (user_id, username, action, resource_type, resource_id, detail, ip_address) "
                    "VALUES (:uid, :uname, :action, :rtype, :rid, :detail, :ip)"
                ),
                {
                    "uid": user_id,
                    "uname": username,
                    "action": action,
                    "rtype": resource_type,
                    "rid": resource_id,
                    "detail": detail,
                    "ip": ip_address,
                }
            )
    except Exception as e:
        logger.warning(f"Failed to write audit log: {e}")
