"""
RAG Analytics API.

Provides detailed analytics for the RAG quality dashboard,
including trend data, distribution analysis, and quality metrics.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text

from app.auth import TokenData, require_role
from app.core.logger import get_logger
from app.storage.database import get_db_session

logger = get_logger(__name__)
router = APIRouter()


@router.get("/quality/trends")
async def get_quality_trends(
    days: int = Query(7, ge=1, le=90),
    current_user: TokenData = Depends(require_role("admin")),
):
    """
    Get RAG quality metrics trends over time.

    Returns daily aggregated metrics for faithfulness, answer_relevance,
    and context_precision.
    """
    try:
        async with get_db_session() as db:
            result = await db.execute(
                text("""
                    SELECT
                        DATE(created_at) as date,
                        COUNT(*) as query_count,
                        AVG(faithfulness) as avg_faithfulness,
                        AVG(answer_relevance) as avg_answer_relevance,
                        AVG(context_precision) as avg_context_precision,
                        AVG(latency_ms) as avg_latency,
                        SUM(tokens_used) as total_tokens
                    FROM evaluations
                    WHERE created_at >= DATE_SUB(NOW(), INTERVAL :days DAY)
                    GROUP BY DATE(created_at)
                    ORDER BY date ASC
                """),
                {"days": days},
            )
            rows = result.fetchall()

            trends = [
                {
                    "date": row[0].isoformat() if row[0] else None,
                    "query_count": row[1],
                    "faithfulness": round(float(row[2] or 0), 3),
                    "answer_relevance": round(float(row[3] or 0), 3),
                    "context_precision": round(float(row[4] or 0), 3),
                    "avg_latency_ms": round(float(row[5] or 0), 1),
                    "total_tokens": row[6] or 0,
                }
                for row in rows
            ]

            return {"period_days": days, "trends": trends}

    except Exception as e:
        logger.error("Failed to get quality trends", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get quality trends")


@router.get("/quality/distribution")
async def get_quality_distribution(
    days: int = Query(7, ge=1, le=30),
    current_user: TokenData = Depends(require_role("admin")),
):
    """
    Get distribution of quality scores.

    Returns histogram buckets for each metric.
    """
    try:
        async with get_db_session() as db:
            # Get all scores for the period
            result = await db.execute(
                text("""
                    SELECT faithfulness, answer_relevance, context_precision
                    FROM evaluations
                    WHERE created_at >= DATE_SUB(NOW(), INTERVAL :days DAY)
                    AND faithfulness IS NOT NULL
                """),
                {"days": days},
            )
            rows = result.fetchall()

            # Build distribution buckets
            def build_histogram(values: list[float], bucket_size: float = 0.1) -> dict[str, int]:
                buckets = {}
                for i in range(10):
                    low = i * bucket_size
                    high = (i + 1) * bucket_size
                    label = f"{low:.1f}-{high:.1f}"
                    buckets[label] = 0

                for v in values:
                    if v is not None:
                        bucket_idx = min(int(v / bucket_size), 9)
                        low = bucket_idx * bucket_size
                        high = (bucket_idx + 1) * bucket_size
                        label = f"{low:.1f}-{high:.1f}"
                        buckets[label] = buckets.get(label, 0) + 1

                return buckets

            faithfulness_vals = [r[0] for r in rows if r[0] is not None]
            relevance_vals = [r[1] for r in rows if r[1] is not None]
            precision_vals = [r[2] for r in rows if r[2] is not None]

            return {
                "period_days": days,
                "total_evaluations": len(rows),
                "distributions": {
                    "faithfulness": build_histogram(faithfulness_vals),
                    "answer_relevance": build_histogram(relevance_vals),
                    "context_precision": build_histogram(precision_vals),
                },
            }

    except Exception as e:
        logger.error("Failed to get quality distribution", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get quality distribution")


@router.get("/quality/latency")
async def get_latency_stats(
    days: int = Query(7, ge=1, le=30),
    current_user: TokenData = Depends(require_role("admin")),
):
    """
    Get latency statistics and percentiles.
    """
    try:
        async with get_db_session() as db:
            result = await db.execute(
                text("""
                    SELECT latency_ms
                    FROM evaluations
                    WHERE created_at >= DATE_SUB(NOW(), INTERVAL :days DAY)
                    AND latency_ms IS NOT NULL
                    ORDER BY latency_ms ASC
                """),
                {"days": days},
            )
            latencies = [r[0] for r in result.fetchall()]

            if not latencies:
                return {
                    "period_days": days,
                    "count": 0,
                    "stats": None,
                }

            import statistics

            # Calculate percentiles
            def percentile(data: list[int], p: float) -> int:
                k = (len(data) - 1) * (p / 100)
                f = int(k)
                c = f + 1
                if c >= len(data):
                    return data[-1]
                return int(data[f] + (k - f) * (data[c] - data[f]))

            return {
                "period_days": days,
                "count": len(latencies),
                "stats": {
                    "min": min(latencies),
                    "max": max(latencies),
                    "mean": round(statistics.mean(latencies), 1),
                    "median": round(statistics.median(latencies), 1),
                    "p90": percentile(latencies, 90),
                    "p95": percentile(latencies, 95),
                    "p99": percentile(latencies, 99),
                },
            }

    except Exception as e:
        logger.error("Failed to get latency stats", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get latency stats")


@router.get("/retrieval/stats")
async def get_retrieval_stats(
    days: int = Query(7, ge=1, le=30),
    current_user: TokenData = Depends(require_role("admin")),
):
    """
    Get retrieval performance statistics.
    """
    try:
        async with get_db_session() as db:
            # Get retrieval stats from evaluations
            result = await db.execute(
                text("""
                    SELECT
                        COUNT(*) as total_queries,
                        AVG(context_precision) as avg_precision,
                        MIN(context_precision) as min_precision,
                        MAX(context_precision) as max_precision
                    FROM evaluations
                    WHERE created_at >= DATE_SUB(NOW(), INTERVAL :days DAY)
                    AND context_precision IS NOT NULL
                """),
                {"days": days},
            )
            stats = result.fetchone()

            # Get intent distribution from skill logs
            intent_result = await db.execute(
                text("""
                    SELECT skill_name, COUNT(*) as count
                    FROM skill_logs
                    WHERE created_at >= DATE_SUB(NOW(), INTERVAL :days DAY)
                    GROUP BY skill_name
                    ORDER BY count DESC
                """),
                {"days": days},
            )
            intents = [
                {"skill": row[0], "count": row[1]}
                for row in intent_result.fetchall()
            ]

            return {
                "period_days": days,
                "retrieval": {
                    "total_queries": stats[0] or 0,
                    "avg_precision": round(float(stats[1] or 0), 3),
                    "min_precision": round(float(stats[2] or 0), 3),
                    "max_precision": round(float(stats[3] or 0), 3),
                },
                "intent_distribution": intents,
            }

    except Exception as e:
        logger.error("Failed to get retrieval stats", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get retrieval stats")


@router.get("/tokens/usage")
async def get_token_usage(
    days: int = Query(7, ge=1, le=30),
    current_user: TokenData = Depends(require_role("admin")),
):
    """
    Get token usage statistics.
    """
    try:
        async with get_db_session() as db:
            result = await db.execute(
                text("""
                    SELECT
                        DATE(created_at) as date,
                        SUM(tokens_used) as daily_tokens,
                        COUNT(*) as query_count
                    FROM evaluations
                    WHERE created_at >= DATE_SUB(NOW(), INTERVAL :days DAY)
                    GROUP BY DATE(created_at)
                    ORDER BY date ASC
                """),
                {"days": days},
            )
            rows = result.fetchall()

            usage = [
                {
                    "date": row[0].isoformat() if row[0] else None,
                    "tokens": row[1] or 0,
                    "queries": row[2] or 0,
                }
                for row in rows
            ]

            total_tokens = sum(u["tokens"] for u in usage)
            total_queries = sum(u["queries"] for u in usage)

            return {
                "period_days": days,
                "total_tokens": total_tokens,
                "total_queries": total_queries,
                "avg_tokens_per_query": round(total_tokens / max(total_queries, 1), 1),
                "daily_usage": usage,
            }

    except Exception as e:
        logger.error("Failed to get token usage", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get token usage")
