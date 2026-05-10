"""
Admin API for system management.
User management, system stats, configuration, and monitoring.
"""
from datetime import UTC, datetime

from app.core.logger import get_logger

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text

from app.auth import TokenData, auth_handler, get_current_user, require_role
from app.config import settings
from app.core.metrics import get_metrics_summary
from app.rag.retriever import retriever
from app.rag.vector_store import vector_store
from app.storage.database import get_db_session
from app.storage.redis_client import redis_client

logger = get_logger(__name__)

router = APIRouter()


class UserCreate(BaseModel):
    username: str
    email: str | None = None
    role: str = "user"
    password: str


class UserUpdate(BaseModel):
    email: str | None = None
    role: str | None = None
    is_active: bool | None = None


class UserResponse(BaseModel):
    id: str
    username: str
    email: str | None
    role: str
    is_active: bool
    api_key: str | None
    created_at: datetime


class SystemStats(BaseModel):
    users: int
    knowledge_bases: int
    documents: int
    chunks: int
    sessions: int
    messages: int
    evaluations: int


class RetrievalConfigUpdate(BaseModel):
    vector_weight: float | None = None
    bm25_weight: float | None = None
    top_k: int | None = None
    rerank_enabled: bool | None = None
    self_rag_enabled: bool | None = None


# === User Management ===

@router.get("/users", response_model=list[UserResponse])
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: TokenData = Depends(require_role("admin")),
):
    """List all users (admin only)."""
    async with get_db_session() as db:
        result = await db.execute(
            text("SELECT id, username, email, role, is_active, api_key, created_at "
                 "FROM users ORDER BY created_at DESC LIMIT :limit OFFSET :skip"),
            {"limit": limit, "skip": skip}
        )
        users = result.fetchall()
        return [
            UserResponse(
                id=u[0],
                username=u[1],
                email=u[2],
                role=u[3],
                is_active=u[4],
                api_key=u[5],
                created_at=u[6],
            )
            for u in users
        ]


@router.post("/users", response_model=UserResponse)
async def create_user(
    user: UserCreate,
    current_user: TokenData = Depends(require_role("admin")),
):
    """Create a new user (admin only)."""
    import uuid

    from app.api.auth import hash_password

    user_id = str(uuid.uuid4())
    api_key = auth_handler.generate_api_key() if user.role == "admin" else None
    password_hash = hash_password(user.password)

    async with get_db_session() as db:
        try:
            await db.execute(
                text("INSERT INTO users (id, username, email, role, api_key, password_hash) "
                     "VALUES (:id, :username, :email, :role, :api_key, :hash)"),
                {
                    "id": user_id,
                    "username": user.username,
                    "email": user.email,
                    "role": user.role,
                    "api_key": api_key,
                    "hash": password_hash,
                }
            )

            return UserResponse(
                id=user_id,
                username=user.username,
                email=user.email,
                role=user.role,
                is_active=True,
                api_key=api_key,
                created_at=datetime.now(UTC),
            )
        except Exception as e:
            raise HTTPException(400, f"Failed to create user: {e}")


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    current_user: TokenData = Depends(require_role("admin")),
):
    """Get user details (admin only)."""
    async with get_db_session() as db:
        result = await db.execute(
            text("SELECT id, username, email, role, is_active, api_key, created_at "
                 "FROM users WHERE id=:user_id"),
            {"user_id": user_id}
        )
        u = result.fetchone()
        if not u:
            raise HTTPException(404, "User not found")

        return UserResponse(
            id=u[0],
            username=u[1],
            email=u[2],
            role=u[3],
            is_active=u[4],
            api_key=u[5],
            created_at=u[6],
        )


@router.put("/users/{user_id}")
async def update_user(
    user_id: str,
    update: UserUpdate,
    current_user: TokenData = Depends(require_role("admin")),
):
    """Update user (admin only)."""
    async with get_db_session() as db:
        # Build dynamic update
        updates = []
        params = {"user_id": user_id}

        if update.email is not None:
            updates.append("email=:email")
            params["email"] = update.email
        if update.role is not None:
            updates.append("role=:role")
            params["role"] = update.role
        if update.is_active is not None:
            updates.append("is_active=:is_active")
            params["is_active"] = update.is_active

        if not updates:
            return {"status": "no changes"}

        await db.execute(
            text(f"UPDATE users SET {', '.join(updates)} WHERE id=:user_id"),
            params
        )

        return {"status": "updated", "user_id": user_id}


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    current_user: TokenData = Depends(require_role("admin")),
):
    """Delete user (admin only)."""
    if user_id == current_user.user_id:
        raise HTTPException(400, "Cannot delete yourself")

    async with get_db_session() as db:
        await db.execute(
            text("DELETE FROM users WHERE id=:user_id"),
            {"user_id": user_id}
        )

        return {"status": "deleted", "user_id": user_id}


@router.post("/users/{user_id}/reset-api-key")
async def reset_api_key(
    user_id: str,
    current_user: TokenData = Depends(require_role("admin")),
):
    """Reset user API key (admin only)."""
    new_key = auth_handler.generate_api_key()

    async with get_db_session() as db:
        await db.execute(
            text("UPDATE users SET api_key=:api_key WHERE id=:user_id"),
            {"api_key": new_key, "user_id": user_id}
        )

        return {"api_key": new_key, "user_id": user_id}


# === System Statistics ===

@router.get("/stats", response_model=SystemStats)
async def get_system_stats(
    current_user: TokenData = Depends(require_role("admin")),
):
    """Get system statistics (admin only)."""
    async with get_db_session() as db:
        # Count users
        result = await db.execute(text("SELECT COUNT(*) FROM users"))
        users = result.fetchone()[0]

        # Count knowledge bases
        result = await db.execute(text("SELECT COUNT(*) FROM knowledges"))
        knowledge_bases = result.fetchone()[0]

        # Count documents
        result = await db.execute(text("SELECT COUNT(*) FROM documents"))
        documents = result.fetchone()[0]

        # Count chunks
        result = await db.execute(text("SELECT COUNT(*) FROM chunks"))
        chunks = result.fetchone()[0]

        # Count sessions
        result = await db.execute(text("SELECT COUNT(*) FROM sessions"))
        sessions = result.fetchone()[0]

        # Count messages
        result = await db.execute(text("SELECT COUNT(*) FROM messages"))
        messages = result.fetchone()[0]

        # Count evaluations
        result = await db.execute(text("SELECT COUNT(*) FROM evaluations"))
        evaluations = result.fetchone()[0]

        return SystemStats(
            users=users,
            knowledge_bases=knowledge_bases,
            documents=documents,
            chunks=chunks,
            sessions=sessions,
            messages=messages,
            evaluations=evaluations,
        )


@router.get("/metrics")
async def get_metrics(
    current_user: TokenData = Depends(require_role("admin")),
):
    """Get Prometheus-style metrics (admin only)."""
    return get_metrics_summary()


@router.get("/vector-store/stats")
async def get_vector_store_stats(
    current_user: TokenData = Depends(require_role("admin")),
):
    """Get vector store statistics (admin only)."""
    return vector_store.get_stats()


@router.get("/redis/stats")
async def get_redis_stats(
    current_user: TokenData = Depends(require_role("admin")),
):
    """Get Redis statistics (admin only)."""
    if not redis_client.is_connected:
        return {"connected": False}

    try:
        info = await redis_client.client.info()
        return {
            "connected": True,
            "used_memory": info.get("used_memory_human", "unknown"),
            "connected_clients": info.get("connected_clients", 0),
            "total_commands_processed": info.get("total_commands_processed", 0),
            "keyspace_hits": info.get("keyspace_hits", 0),
            "keyspace_misses": info.get("keyspace_misses", 0),
        }
    except Exception as e:
        return {"connected": False, "error": str(e)}


# === Retrieval Configuration ===

@router.get("/retrieval-config")
async def get_retrieval_config(
    knowledge_id: str | None = None,
    current_user: TokenData = Depends(get_current_user),
):
    """Get retrieval configuration."""
    async with get_db_session() as db:
        if knowledge_id:
            result = await db.execute(
                text("SELECT vector_weight, bm25_weight, top_k, rerank_enabled, self_rag_enabled "
                     "FROM retrieval_configs WHERE knowledge_id=:kid"),
                {"kid": knowledge_id}
            )
            config = result.fetchone()
            if config:
                return {
                    "vector_weight": config[0],
                    "bm25_weight": config[1],
                    "top_k": config[2],
                    "rerank_enabled": config[3],
                    "self_rag_enabled": config[4],
                }

        # Return defaults
        return {
            "vector_weight": settings.DEFAULT_VECTOR_WEIGHT,
            "bm25_weight": settings.DEFAULT_BM25_WEIGHT,
            "top_k": 10,
            "rerank_enabled": True,
            "self_rag_enabled": True,
        }


@router.put("/retrieval-config")
async def update_retrieval_config(
    knowledge_id: str | None = None,
    config: RetrievalConfigUpdate = None,
    current_user: TokenData = Depends(get_current_user),
):
    """Update retrieval configuration."""
    import uuid

    # Update global retriever weights
    if config.vector_weight is not None and config.bm25_weight is not None:
        retriever.set_weights(config.vector_weight, config.bm25_weight)

    async with get_db_session() as db:
        config_id = str(uuid.uuid4())

        # Upsert config
        await db.execute(
            text("""
                INSERT INTO retrieval_configs
                    (id, user_id, knowledge_id, vector_weight, bm25_weight, top_k,
                     rerank_enabled, self_rag_enabled)
                VALUES (:id, :user_id, :kid, :vw, :bw, :top_k, :rerank, :self_rag)
                ON DUPLICATE KEY UPDATE
                    vector_weight=:vw, bm25_weight=:bw, top_k=:top_k,
                    rerank_enabled=:rerank, self_rag_enabled=:self_rag
            """),
            {
                "id": config_id,
                "user_id": current_user.user_id,
                "kid": knowledge_id,
                "vw": config.vector_weight if config.vector_weight is not None else settings.DEFAULT_VECTOR_WEIGHT,
                "bw": config.bm25_weight if config.bm25_weight is not None else settings.DEFAULT_BM25_WEIGHT,
                "top_k": config.top_k if config.top_k is not None else 10,
                "rerank": config.rerank_enabled if config.rerank_enabled is not None else True,
                "self_rag": config.self_rag_enabled if config.self_rag_enabled is not None else True,
            }
        )

        return {"status": "updated"}


# === Evaluation Analytics ===

@router.get("/evaluations")
async def list_evaluations(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    days: int = Query(7, ge=1, le=30),
    current_user: TokenData = Depends(require_role("admin")),
):
    """List recent evaluations (admin only)."""
    async with get_db_session() as db:
        result = await db.execute(
            text("""
                SELECT id, query, answer, faithfulness, answer_relevance,
                       context_precision, latency_ms, tokens_used, created_at
                FROM evaluations
                WHERE created_at >= DATE_SUB(NOW(), INTERVAL :days DAY)
                ORDER BY created_at DESC
                LIMIT :limit OFFSET :skip
            """),
            {"days": days, "limit": limit, "skip": skip}
        )
        evals = result.fetchall()

        return [
            {
                "id": e[0],
                "query": (e[1] or "")[:100] + "..." if len(e[1] or "") > 100 else (e[1] or ""),
                "answer": (e[2] or "")[:100] + "..." if len(e[2] or "") > 100 else (e[2] or ""),
                "faithfulness": e[3],
                "answer_relevance": e[4],
                "context_precision": e[5],
                "latency_ms": e[6],
                "tokens_used": e[7],
                "created_at": e[8].isoformat() if e[8] else None,
            }
            for e in evals
        ]


@router.get("/evaluations/summary")
async def get_evaluation_summary(
    days: int = Query(7, ge=1, le=30),
    current_user: TokenData = Depends(require_role("admin")),
):
    """Get evaluation metrics summary (admin only)."""
    async with get_db_session() as db:
        result = await db.execute(
            text("""
                SELECT
                    COUNT(*) as total,
                    AVG(faithfulness) as avg_faithfulness,
                    AVG(answer_relevance) as avg_answer_relevance,
                    AVG(context_precision) as avg_context_precision,
                    AVG(latency_ms) as avg_latency_ms,
                    SUM(tokens_used) as total_tokens
                FROM evaluations
                WHERE created_at >= DATE_SUB(NOW(), INTERVAL :days DAY)
            """),
            {"days": days}
        )
        row = result.fetchone()

        return {
            "period_days": days,
            "total_evaluations": row[0] or 0,
            "avg_faithfulness": round(row[1] or 0, 3),
            "avg_answer_relevance": round(row[2] or 0, 3),
            "avg_context_precision": round(row[3] or 0, 3),
            "avg_latency_ms": round(row[4] or 0, 1),
            "total_tokens": row[5] or 0,
        }


# === Skill Logs ===

@router.get("/skill-logs")
async def list_skill_logs(
    skill_name: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: TokenData = Depends(require_role("admin")),
):
    """List skill execution logs (admin only)."""
    async with get_db_session() as db:
        if skill_name:
            result = await db.execute(
                text("""
                    SELECT id, skill_name, input_params, output_result, latency_ms, success, error_message, created_at
                    FROM skill_logs
                    WHERE skill_name=:skill_name
                    ORDER BY created_at DESC
                    LIMIT :limit OFFSET :skip
                """),
                {"skill_name": skill_name, "limit": limit, "skip": skip}
            )
        else:
            result = await db.execute(
                text("""
                    SELECT id, skill_name, input_params, output_result, latency_ms, success, error_message, created_at
                    FROM skill_logs
                    ORDER BY created_at DESC
                    LIMIT :limit OFFSET :skip
                """),
                {"limit": limit, "skip": skip}
            )

        logs = result.fetchall()
        return [
            {
                "id": log[0],
                "skill_name": log[1],
                "input_params": log[2],
                "output_result": log[3],
                "latency_ms": log[4],
                "success": log[5],
                "error_message": log[6],
                "created_at": log[7].isoformat() if log[7] else None,
            }
            for log in logs
        ]


@router.get("/skill-stats")
async def get_skill_stats(
    current_user: TokenData = Depends(require_role("admin")),
):
    """
    Get real-time skill usage statistics (admin only).

    Combines in-memory telemetry (current process) with persisted logs (historical).
    """
    from app.skills.registry import registry

    # In-memory telemetry from current process
    live_stats = registry.get_stats()

    # Historical stats from database
    async with get_db_session() as db:
        result = await db.execute(
            text("""
                SELECT
                    skill_name,
                    COUNT(*) as total_calls,
                    SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as success_count,
                    AVG(latency_ms) as avg_latency_ms,
                    MAX(created_at) as last_called_at
                FROM skill_logs
                WHERE created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
                GROUP BY skill_name
            """)
        )
        rows = result.fetchall()

    historical = {}
    for row in rows:
        historical[row[0]] = {
            "total_calls_30d": row[1],
            "success_count_30d": row[2],
            "success_rate_30d": round(row[2] / row[1], 3) if row[1] > 0 else 0,
            "avg_latency_ms_30d": round(row[3] or 0, 1),
            "last_called_at": row[4].isoformat() if row[4] else None,
        }

    # Merge live + historical
    all_skills = set(list(live_stats.keys()) + list(historical.keys()))
    merged = {}
    for name in all_skills:
        merged[name] = {
            "live": live_stats.get(name, {}),
            "historical": historical.get(name, {}),
        }

    return {"skills": merged}


# === Audit Logs ===

@router.get("/audit-logs")
async def list_audit_logs(
    action: str | None = None,
    user_id: str | None = None,
    resource_type: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: TokenData = Depends(require_role("admin")),
):
    """List audit logs with optional filters (admin only)."""
    conditions = []
    params = {"limit": limit, "skip": skip}

    if action:
        conditions.append("action = :action")
        params["action"] = action
    if user_id:
        conditions.append("user_id = :uid")
        params["uid"] = user_id
    if resource_type:
        conditions.append("resource_type = :rtype")
        params["rtype"] = resource_type

    where = "WHERE " + " AND ".join(conditions) if conditions else ""

    async with get_db_session() as db:
        result = await db.execute(
            text(f"SELECT id, user_id, username, action, resource_type, resource_id, detail, ip_address, created_at "
                 f"FROM audit_logs {where} ORDER BY created_at DESC LIMIT :limit OFFSET :skip"),
            params
        )
        logs = result.fetchall()

        # Get total count
        count_result = await db.execute(
            text(f"SELECT COUNT(*) FROM audit_logs {where}"),
            params
        )
        total = count_result.fetchone()[0]

        return {
            "total": total,
            "logs": [
                {
                    "id": log[0],
                    "user_id": log[1],
                    "username": log[2],
                    "action": log[3],
                    "resource_type": log[4],
                    "resource_id": log[5],
                    "detail": log[6],
                    "ip_address": log[7],
                    "created_at": log[8].isoformat() if log[8] else None,
                }
                for log in logs
            ]
        }


@router.get("/audit-logs/actions")
async def list_audit_actions(
    current_user: TokenData = Depends(require_role("admin")),
):
    """List distinct audit log action types."""
    async with get_db_session() as db:
        result = await db.execute(
            text("SELECT DISTINCT action FROM audit_logs ORDER BY action")
        )
        return {"actions": [row[0] for row in result.fetchall()]}


# === System Configuration ===

@router.get("/config")
async def get_system_config(
    current_user: TokenData = Depends(require_role("admin")),
):
    """Get system configuration (admin only)."""
    return {
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "debug": settings.DEBUG,
        "embedding_model": settings.EMBEDDING_MODEL,
        "embedding_dim": settings.EMBEDDING_DIM,
        "llm_model": settings.LLM_MODEL,
        "chunk_size": settings.CHUNK_SIZE,
        "chunk_overlap": settings.CHUNK_OVERLAP,
        "vector_store": settings.VECTOR_STORE,
        "max_iterations": settings.MAX_ITERATIONS,
        "agent_timeout": settings.AGENT_TIMEOUT,
    }


@router.get("/health")
async def health_check():
    """Public health check endpoint."""
    checks = {
        "api": "ok",
        "database": "unknown",
        "redis": "unknown",
        "vector_store": "unknown",
    }

    # Check database
    try:
        async with get_db_session() as db:
            await db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"

    # Check Redis
    if redis_client.is_connected:
        checks["redis"] = "ok"
    else:
        checks["redis"] = "disconnected"

    # Check vector store
    stats = vector_store.get_stats()
    checks["vector_store"] = "ok" if stats.get("connected") else "disconnected"

    all_ok = all(v == "ok" for v in checks.values())
    return {
        "status": "healthy" if all_ok else "degraded",
        "checks": checks,
        "timestamp": datetime.now(UTC).isoformat(),
    }


# ── System Settings ──

class SystemSettingsUpdate(BaseModel):
    llm_model: str | None = None
    embedding_model: str | None = None
    chunk_size: int | None = None
    chunk_overlap: int | None = None
    max_upload_size_mb: int | None = None
    default_vector_weight: float | None = None
    default_bm25_weight: float | None = None


# === Self-service API Key ===

@router.get("/api-key")
async def get_my_api_key(
    current_user: TokenData = Depends(get_current_user),
):
    """Get current user's API key."""
    async with get_db_session() as db:
        result = await db.execute(
            text("SELECT api_key FROM users WHERE id=:uid"),
            {"uid": current_user.user_id}
        )
        row = result.fetchone()
        return {"api_key": row[0] if row else None}


@router.post("/api-key")
async def generate_my_api_key(
    current_user: TokenData = Depends(get_current_user),
):
    """Generate or regenerate current user's API key."""
    new_key = auth_handler.generate_api_key()
    async with get_db_session() as db:
        await db.execute(
            text("UPDATE users SET api_key=:key WHERE id=:uid"),
            {"key": new_key, "uid": current_user.user_id}
        )
    return {"api_key": new_key}


@router.delete("/api-key")
async def revoke_my_api_key(
    current_user: TokenData = Depends(get_current_user),
):
    """Revoke current user's API key."""
    async with get_db_session() as db:
        await db.execute(
            text("UPDATE users SET api_key=NULL WHERE id=:uid"),
            {"uid": current_user.user_id}
        )
    return {"status": "revoked"}


# === System Settings ===

@router.get("/settings")
async def get_system_settings(
    current_user: TokenData = Depends(require_role("admin")),
):
    """Get current system settings."""
    return {
        "llm_model": settings.LLM_MODEL,
        "embedding_model": settings.EMBEDDING_MODEL,
        "chunk_size": settings.CHUNK_SIZE,
        "chunk_overlap": settings.CHUNK_OVERLAP,
        "max_upload_size_mb": settings.MAX_UPLOAD_SIZE_MB,
        "default_vector_weight": settings.DEFAULT_VECTOR_WEIGHT,
        "default_bm25_weight": settings.DEFAULT_BM25_WEIGHT,
        "available_models": settings.AVAILABLE_MODELS,
        "embedding_dim": settings.EMBEDDING_DIM,
        "max_iterations": settings.MAX_ITERATIONS,
        "agent_timeout": settings.AGENT_TIMEOUT,
    }


@router.put("/settings")
async def update_system_settings(
    req: SystemSettingsUpdate,
    current_user: TokenData = Depends(require_role("admin")),
):
    """Update system settings (runtime only, not persisted to .env)."""
    updated = {}
    if req.llm_model is not None:
        settings.LLM_MODEL = req.llm_model
        updated["llm_model"] = req.llm_model
    if req.embedding_model is not None:
        settings.EMBEDDING_MODEL = req.embedding_model
        updated["embedding_model"] = req.embedding_model
    if req.chunk_size is not None:
        settings.CHUNK_SIZE = req.chunk_size
        updated["chunk_size"] = req.chunk_size
    if req.chunk_overlap is not None:
        settings.CHUNK_OVERLAP = req.chunk_overlap
        updated["chunk_overlap"] = req.chunk_overlap
    if req.max_upload_size_mb is not None:
        settings.MAX_UPLOAD_SIZE_MB = req.max_upload_size_mb
        updated["max_upload_size_mb"] = req.max_upload_size_mb
    if req.default_vector_weight is not None:
        settings.DEFAULT_VECTOR_WEIGHT = req.default_vector_weight
        updated["default_vector_weight"] = req.default_vector_weight
    if req.default_bm25_weight is not None:
        settings.DEFAULT_BM25_WEIGHT = req.default_bm25_weight
        updated["default_bm25_weight"] = req.default_bm25_weight

    return {"status": "updated", "settings": updated}
