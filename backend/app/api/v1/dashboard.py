"""Legacy dashboard compatibility APIs."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.system import get_metrics_overview, get_retrieval_metrics
from app.core.database import get_read_db
from app.core.request_context import RequestContext, resolve_request_context
from app.models.agent import AgentExecution, AgentStep

router = APIRouter()

_COMPAT_SUNSET = (datetime.now(timezone.utc) + timedelta(days=90)).strftime("%a, %d %b %Y %H:%M:%S GMT")


def get_request_context(request: Request) -> RequestContext:
    return resolve_request_context(request)


def _set_compat_headers(response: Response, replacement: str) -> None:
    response.headers["Deprecation"] = "true"
    response.headers["Sunset"] = _COMPAT_SUNSET
    response.headers["Link"] = f'<{replacement}>; rel="successor-version"'


@router.get("/system")
async def dashboard_system(
    response: Response,
    db: AsyncSession = Depends(get_read_db),
):
    """Compatibility endpoint for legacy `/dashboard/system`."""
    _set_compat_headers(response, "/api/v1/system/metrics/overview")
    # Call the real metrics collector endpoint logic.
    overview = await get_metrics_overview(db)
    timestamp = datetime.now(timezone.utc).isoformat()
    return {
        "qps": [{"timestamp": timestamp, "value": overview["qps"]["current"]}],
        "latency_p50": [{"timestamp": timestamp, "value": overview["latency"]["p50_ms"]}],
        "latency_p99": [{"timestamp": timestamp, "value": overview["latency"]["p99_ms"]}],
        "error_rate": [{"timestamp": timestamp, "value": overview["error_rate"]["rate_5xx"]}],
        "active_connections": overview["active_connections"],
        "services": [
            {
                "name": name,
                "status": svc.get("status", "healthy"),
                "uptime": svc.get("uptime", 1.0),
                "last_check": timestamp,
            }
            for name, svc in overview["services"].items()
        ],
    }


@router.get("/traces/{trace_id}")
async def dashboard_trace(
    trace_id: str,
    response: Response,
    db: AsyncSession = Depends(get_read_db),
    ctx: RequestContext = Depends(get_request_context),
):
    """Compatibility endpoint for legacy `/dashboard/traces/{trace_id}`."""
    _set_compat_headers(response, "/api/v1/agents/trace/{trace_id}")
    execution = await db.scalar(
        select(AgentExecution).where(
            AgentExecution.trace_id == trace_id,
            AgentExecution.tenant_id == ctx.tenant_id,
        )
    )
    if not execution:
        raise HTTPException(status_code=404, detail="trace not found")

    step_rows = (
        await db.scalars(
            select(AgentStep).where(AgentStep.execution_id == execution.id).order_by(AgentStep.step_number.asc())
        )
    ).all()

    status_map = {
        "completed": "success",
        "failed": "error",
        "timeout": "timeout",
    }
    return {
        "trace_id": execution.trace_id,
        "status": status_map.get(execution.status, execution.status),
        "total_duration_ms": float(execution.latency_ms or 0.0),
        "total_tokens": execution.total_tokens_used or 0,
        "steps": [
            {
                "step_id": str(step.id),
                "type": step.step_type,
                "content": step.observation or step.thought or step.action or "",
                "duration_ms": float(step.latency_ms or 0.0),
                "tokens": step.tokens_used or 0,
                "metadata": {
                    "tool_name": step.tool_name,
                    "status": step.status,
                },
            }
            for step in step_rows
        ],
        "created_at": execution.created_at.isoformat() if execution.created_at else None,
    }


@router.get("/retrieval")
async def dashboard_retrieval(
    response: Response,
    db: AsyncSession = Depends(get_read_db),
):
    """Compatibility endpoint for legacy `/dashboard/retrieval`."""
    _set_compat_headers(response, "/api/v1/system/metrics/retrieval")
    metrics = await get_retrieval_metrics(db)
    return {
        "recall_rate": metrics["recall"]["top_10"],
        "precision_rate": metrics["precision"]["top_10"],
        "channels": [
            {
                "name": "vector",
                "k_values": [1, 5, 10],
                "top_k_hit_rate": [
                    metrics["recall"]["top_1"],
                    metrics["recall"]["top_5"],
                    metrics["recall"]["top_10"],
                ],
            },
            {
                "name": "keyword",
                "k_values": [10],
                "top_k_hit_rate": [metrics["precision"]["top_10"]],
            },
        ],
        "rerank_comparison": {
            "before": metrics["rerank_improvement"]["before_mrr"],
            "after": metrics["rerank_improvement"]["after_mrr"],
        },
    }
