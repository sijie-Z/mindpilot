"""
Conversation branching API.

Allows users to branch conversations from any message point,
exploring different retrieval strategies or conversation paths.
"""
import json
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from app.core.logger import get_logger
from app.storage.database import get_db_session

logger = get_logger(__name__)
router = APIRouter()


class BranchCreateRequest(BaseModel):
    """Request to create a branch from a message."""
    session_id: str
    message_id: str
    branch_name: str | None = None


class BranchSwitchRequest(BaseModel):
    """Request to switch to a different branch."""
    session_id: str
    branch_id: str


class BranchResponse(BaseModel):
    """Branch information."""
    id: str
    name: str
    session_id: str
    parent_message_id: str
    message_count: int
    created_at: str


@router.post("/create")
async def create_branch(request: BranchCreateRequest):
    """
    Create a new branch from a specific message.

    This creates a copy of the conversation up to the specified message,
    allowing users to explore different conversation paths.
    """
    try:
        branch_id = str(uuid.uuid4())
        branch_name = request.branch_name or f"分支 {datetime.now().strftime('%H:%M')}"

        async with get_db_session() as db:
            # Verify the message exists
            result = await db.execute(
                text("SELECT id, session_id FROM messages WHERE id = :mid AND session_id = :sid"),
                {"mid": request.message_id, "sid": request.session_id},
            )
            message = result.fetchone()
            if not message:
                raise HTTPException(status_code=404, detail="Message not found")

            # Create branch record
            await db.execute(
                text(
                    "INSERT INTO conversation_branches (id, session_id, parent_message_id, name) "
                    "VALUES (:id, :sid, :pid, :name)"
                ),
                {"id": branch_id, "sid": request.session_id, "pid": request.message_id, "name": branch_name},
            )

            # Copy messages up to the branch point
            await db.execute(
                text(
                    "INSERT INTO messages (id, session_id, role, content, metadata, branch_id, created_at) "
                    "SELECT id, session_id, role, content, metadata, :branch_id, created_at "
                    "FROM messages WHERE session_id = :sid AND created_at <= "
                    "(SELECT created_at FROM messages WHERE id = :mid) "
                    "ORDER BY created_at ASC"
                ),
                {"branch_id": branch_id, "sid": request.session_id, "mid": request.message_id},
            )

            # Count messages in branch
            count_result = await db.execute(
                text("SELECT COUNT(*) FROM messages WHERE branch_id = :bid"),
                {"bid": branch_id},
            )
            message_count = count_result.fetchone()[0]

        logger.info("Branch created", branch_id=branch_id, session_id=request.session_id)
        return {
            "branch_id": branch_id,
            "name": branch_name,
            "session_id": request.session_id,
            "parent_message_id": request.message_id,
            "message_count": message_count,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to create branch", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to create branch")


@router.get("/list/{session_id}")
async def list_branches(session_id: str):
    """List all branches for a session."""
    try:
        async with get_db_session() as db:
            # Get main branch info
            main_result = await db.execute(
                text("SELECT COUNT(*) FROM messages WHERE session_id = :sid AND branch_id IS NULL"),
                {"sid": session_id},
            )
            main_count = main_result.fetchone()[0]

            # Get all branches
            result = await db.execute(
                text(
                    "SELECT b.id, b.name, b.parent_message_id, b.created_at, "
                    "(SELECT COUNT(*) FROM messages WHERE branch_id = b.id) as msg_count "
                    "FROM conversation_branches b WHERE b.session_id = :sid "
                    "ORDER BY b.created_at DESC"
                ),
                {"sid": session_id},
            )
            branches = [
                {
                    "id": row[0],
                    "name": row[1],
                    "parent_message_id": row[2],
                    "created_at": str(row[3]),
                    "message_count": row[4],
                }
                for row in result.fetchall()
            ]

        return {
            "session_id": session_id,
            "main_branch": {"message_count": main_count},
            "branches": branches,
        }

    except Exception as e:
        logger.error("Failed to list branches", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to list branches")


@router.get("/{branch_id}")
async def get_branch(branch_id: str):
    """Get branch messages."""
    try:
        async with get_db_session() as db:
            # Get branch info
            branch_result = await db.execute(
                text(
                    "SELECT id, session_id, parent_message_id, name, created_at "
                    "FROM conversation_branches WHERE id = :bid"
                ),
                {"bid": branch_id},
            )
            branch = branch_result.fetchone()
            if not branch:
                raise HTTPException(status_code=404, detail="Branch not found")

            # Get messages in branch
            msgs_result = await db.execute(
                text(
                    "SELECT id, role, content, metadata, created_at "
                    "FROM messages WHERE branch_id = :bid ORDER BY created_at ASC"
                ),
                {"bid": branch_id},
            )
            messages = [
                {
                    "id": row[0],
                    "role": row[1],
                    "content": row[2],
                    "metadata": row[3] if isinstance(row[3], dict) else json.loads(row[3] or "{}"),
                    "created_at": str(row[4]),
                }
                for row in msgs_result.fetchall()
            ]

        return {
            "branch": {
                "id": branch[0],
                "session_id": branch[1],
                "parent_message_id": branch[2],
                "name": branch[3],
                "created_at": str(branch[4]),
            },
            "messages": messages,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get branch", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get branch")


@router.delete("/{branch_id}")
async def delete_branch(branch_id: str):
    """Delete a branch and its messages."""
    try:
        async with get_db_session() as db:
            # Delete branch messages
            await db.execute(
                text("DELETE FROM messages WHERE branch_id = :bid"),
                {"bid": branch_id},
            )
            # Delete branch record
            await db.execute(
                text("DELETE FROM conversation_branches WHERE id = :bid"),
                {"bid": branch_id},
            )

        return {"status": "deleted", "branch_id": branch_id}

    except Exception as e:
        logger.error("Failed to delete branch", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to delete branch")


@router.post("/switch")
async def switch_branch(request: BranchSwitchRequest):
    """
    Switch to a different branch.

    Returns the messages for the selected branch.
    """
    try:
        async with get_db_session() as db:
            # Verify branch exists
            branch_result = await db.execute(
                text(
                    "SELECT id, session_id, parent_message_id, name "
                    "FROM conversation_branches WHERE id = :bid AND session_id = :sid"
                ),
                {"bid": request.branch_id, "sid": request.session_id},
            )
            branch = branch_result.fetchone()
            if not branch:
                raise HTTPException(status_code=404, detail="Branch not found")

            # Get messages for this branch
            msgs_result = await db.execute(
                text(
                    "SELECT id, role, content, metadata, created_at "
                    "FROM messages WHERE branch_id = :bid ORDER BY created_at ASC"
                ),
                {"bid": request.branch_id},
            )
            messages = [
                {
                    "id": row[0],
                    "role": row[1],
                    "content": row[2],
                    "metadata": row[3] if isinstance(row[3], dict) else json.loads(row[3] or "{}"),
                    "created_at": str(row[4]),
                }
                for row in msgs_result.fetchall()
            ]

        return {
            "branch_id": branch[0],
            "session_id": branch[1],
            "name": branch[3],
            "messages": messages,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to switch branch", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to switch branch")
