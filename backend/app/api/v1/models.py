"""Model configuration APIs backed by relational database."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import case, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_read_db, get_write_db
from app.core.request_context import RequestContext, resolve_request_context
from app.models.agent import AgentExecution
from app.models.model_config import ABTest, ModelConfig, ModelDeployment
from app.schemas.common import PageResponse
from app.schemas.model_config import (
    ABTestCreate,
    ABTestResponse,
    ModelConfigCreate,
    ModelConfigResponse,
    ModelConfigUpdate,
    ModelDeploymentCreate,
    ModelDeploymentResponse,
)
from app.services.deployment_metrics_service import (
    DeploymentLiveMetrics,
    fetch_deployment_live_metrics,
)

router = APIRouter()

_COMPAT_SUNSET = (datetime.now(timezone.utc) + timedelta(days=90)).strftime("%a, %d %b %Y %H:%M:%S GMT")


def get_request_context(request: Request) -> RequestContext:
    return resolve_request_context(request)


def _set_compat_headers(response: Response, replacement: str) -> None:
    response.headers["Deprecation"] = "true"
    response.headers["Sunset"] = _COMPAT_SUNSET
    response.headers["Link"] = f'<{replacement}>; rel="successor-version"'


def _parse_uuid(value: str, field_name: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"invalid {field_name}") from exc


def _model_config_response(
    row: ModelConfig,
    *,
    live_metrics: dict[str, float | None] | None = None,
) -> ModelConfigResponse:
    """Serialize a ModelConfig row.

    When ``live_metrics`` is supplied, the performance fields (avg_latency_ms /
    avg_tokens_per_second / error_rate / quality_score) are taken from the
    freshly-computed aggregate over ``agent_executions`` rather than the
    static columns on ``model_configs`` (which are never updated after
    insert and would otherwise be stale).
    """
    if live_metrics is not None:
        avg_latency_ms = live_metrics.get("avg_latency_ms")
        avg_tokens_per_second = live_metrics.get("avg_tokens_per_second")
        error_rate = live_metrics.get("error_rate")
        quality_score = live_metrics.get("quality_score")
    else:
        avg_latency_ms = row.avg_latency_ms
        avg_tokens_per_second = row.avg_tokens_per_second
        error_rate = row.error_rate
        quality_score = row.quality_score

    return ModelConfigResponse(
        id=row.id,
        name=row.name,
        display_name=row.display_name,
        description=row.description or "",
        model_type=row.model_type,
        provider=row.provider,
        model_id=row.model_id,
        temperature=row.temperature,
        top_p=row.top_p,
        max_tokens=row.max_tokens,
        frequency_penalty=row.frequency_penalty,
        presence_penalty=row.presence_penalty,
        stop_sequences=row.stop_sequences or [],
        context_window=row.context_window,
        supports_function_calling=row.supports_function_calling,
        supports_streaming=row.supports_streaming,
        timeout_seconds=row.timeout_seconds,
        max_retries=row.max_retries,
        max_concurrent_requests=row.max_concurrent_requests,
        requests_per_minute=row.requests_per_minute,
        api_endpoint=row.api_endpoint,
        extra_headers=row.extra_headers or {},
        is_active=row.is_active,
        is_default=row.is_default,
        version=row.version,
        avg_latency_ms=avg_latency_ms,
        avg_tokens_per_second=avg_tokens_per_second,
        error_rate=error_rate,
        quality_score=quality_score,
        extra_config=row.extra_config or {},
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _deployment_response(
    row: ModelDeployment,
    *,
    live_metrics: DeploymentLiveMetrics | None = None,
) -> ModelDeploymentResponse:
    """Serialize a ModelDeployment row.

    When ``live_metrics`` is supplied, fields populated from Prometheus /
    K8s (current_qps / avg_latency_ms / p99_latency_ms / cpu_usage /
    memory_usage / ready_replicas) override the static DB columns. A
    ``None`` field inside ``live_metrics`` means "source unreachable" —
    we fall back to the DB column for QPS / latency, leave CPU / MEM as
    ``None`` (UI shows "未接入监控"), and degrade ready_replicas to the
    legacy pseudo-calc so the副本 column keeps rendering.
    """
    qps = row.current_qps
    avg_lat = row.avg_latency_ms
    p99_lat = row.p99_latency_ms
    cpu_usage: float | None = None
    memory_usage: float | None = None
    ready_replicas: int | None = None

    if live_metrics is not None:
        if live_metrics.current_qps is not None:
            qps = live_metrics.current_qps
        if live_metrics.avg_latency_ms is not None:
            avg_lat = live_metrics.avg_latency_ms
        if live_metrics.p99_latency_ms is not None:
            p99_lat = live_metrics.p99_latency_ms
        cpu_usage = live_metrics.cpu_usage
        memory_usage = live_metrics.memory_usage
        ready_replicas = live_metrics.ready_replicas

    if ready_replicas is None:
        ready_replicas = (
            row.replicas
            if row.status == "running" and row.health_status == "healthy"
            else 0
        )

    return ModelDeploymentResponse(
        id=row.id,
        model_config_id=row.model_config_id,
        deployment_name=row.deployment_name,
        deployment_type=row.deployment_type,
        endpoint_url=row.endpoint_url,
        replicas=row.replicas,
        gpu_type=row.gpu_type,
        gpu_count=row.gpu_count,
        status=row.status,
        health_status=row.health_status,
        current_qps=qps,
        max_qps=row.max_qps,
        avg_latency_ms=avg_lat,
        p99_latency_ms=p99_lat,
        ready_replicas=ready_replicas,
        cpu_usage=cpu_usage,
        memory_usage=memory_usage,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def _safe_live_metrics(
    rows: list[ModelDeployment],
) -> dict[uuid.UUID, DeploymentLiveMetrics]:
    """Best-effort live-metrics batch. Never raises.

    The service is already exception-safe internally, but this extra
    guard means a programming error or import-time failure cannot crash
    the deployment-listing endpoints.
    """
    try:
        return await fetch_deployment_live_metrics(rows)
    except Exception:  # noqa: BLE001
        return {}


def _ab_test_response(row: ABTest) -> ABTestResponse:
    return ABTestResponse(
        id=row.id,
        name=row.name,
        description=row.description or "",
        test_type=row.test_type,
        control_config_id=row.control_config_id,
        treatment_config_id=row.treatment_config_id,
        traffic_split=row.traffic_split,
        primary_metric=row.primary_metric,
        control_metrics=row.control_metrics or {},
        treatment_metrics=row.treatment_metrics or {},
        winner=row.winner,
        status=row.status,
        started_at=row.started_at,
        ended_at=row.ended_at,
        created_at=row.created_at,
    )


def _period_window(period: str) -> tuple[datetime, int]:
    now = datetime.now(timezone.utc)
    normalized = (period or "24h").lower()
    if normalized in {"1h", "hour"}:
        return now - timedelta(hours=1), 12
    if normalized in {"7d", "week"}:
        return now - timedelta(days=7), 7
    if normalized in {"30d", "month"}:
        return now - timedelta(days=30), 30
    return now - timedelta(hours=24), 12


def _bucket_values(values: list[float]) -> dict[str, float]:
    if not values:
        return {"p50": 0.0, "p99": 0.0, "avg": 0.0}
    ordered = sorted(values)
    p50 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.5))]
    p99 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.99))]
    return {
        "p50": round(p50, 2),
        "p99": round(p99, 2),
        "avg": round(sum(ordered) / len(ordered), 2),
    }


def _execution_quality(row: AgentExecution) -> float | None:
    scores = [score for score in [row.relevance_score, row.factuality_score] if score is not None]
    if not scores:
        evaluation = (row.result_metadata or {}).get("evaluation") or {}
        if isinstance(evaluation, dict):
            scores = [
                float(value)
                for key, value in evaluation.items()
                if key in {"relevance", "factuality", "completeness", "clarity"} and value is not None
            ]
    return (sum(scores) / len(scores)) if scores else None


async def _model_execution_rows(
    db: AsyncSession,
    *,
    tenant_id: str,
    model_config_id: uuid.UUID,
    since: datetime,
) -> list[AgentExecution]:
    rows = (
        await db.scalars(
            select(AgentExecution)
            .where(
                AgentExecution.tenant_id == tenant_id,
                AgentExecution.model_config_id == model_config_id,
                AgentExecution.created_at >= since,
            )
            .order_by(AgentExecution.created_at.asc())
            .limit(10000)
        )
    ).all()
    return list(rows)


def _model_metrics_timeseries(rows: list[AgentExecution], *, since: datetime, bucket_count: int) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    total_seconds = max(1.0, (now - since).total_seconds())
    bucket_seconds = max(1.0, total_seconds / bucket_count)
    buckets: list[list[AgentExecution]] = [[] for _ in range(bucket_count)]
    for row in rows:
        created_at = row.created_at
        if created_at and created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        offset = max(0.0, ((created_at or now) - since).total_seconds())
        index = min(bucket_count - 1, int(offset // bucket_seconds))
        buckets[index].append(row)

    timestamps: list[str] = []
    latency_p50: list[float] = []
    latency_p99: list[float] = []
    qps: list[float] = []
    error_rate: list[float] = []
    quality_score: list[float] = []
    for idx, bucket in enumerate(buckets):
        timestamps.append((since + timedelta(seconds=bucket_seconds * idx)).isoformat())
        latency = _bucket_values([float(item.generation_latency_ms or item.latency_ms or 0.0) for item in bucket])
        latency_p50.append(latency["p50"])
        latency_p99.append(latency["p99"])
        qps.append(round(len(bucket) / bucket_seconds, 4))
        error_rate.append(round(sum(1 for item in bucket if item.status == "failed") / len(bucket), 4) if bucket else 0.0)
        qualities = [quality for item in bucket if (quality := _execution_quality(item)) is not None]
        quality_score.append(round(sum(qualities) / len(qualities), 4) if qualities else 0.0)

    return {
        "timestamps": timestamps,
        "latency_p50": latency_p50,
        "latency_p99": latency_p99,
        "qps": qps,
        "error_rate": error_rate,
        "quality_score": quality_score,
    }


def _model_metrics_summary(rows: list[AgentExecution]) -> dict[str, float]:
    latencies = [float(row.generation_latency_ms or row.latency_ms or 0.0) for row in rows]
    qualities = [quality for row in rows if (quality := _execution_quality(row)) is not None]
    return {
        "requests": len(rows),
        "quality_score": round(sum(qualities) / len(qualities), 4) if qualities else 0.0,
        "latency_ms": round(sum(latencies) / len(latencies), 2) if latencies else 0.0,
        "error_rate": round(sum(1 for row in rows if row.status == "failed") / len(rows), 4) if rows else 0.0,
    }


async def _aggregate_recent_model_metrics(
    db: AsyncSession,
    *,
    tenant_id: str,
    model_ids: list[uuid.UUID],
    since: datetime,
) -> dict[uuid.UUID, dict[str, float | None]]:
    """Compute live performance metrics for a batch of model_config_ids.

    Returns a mapping ``{model_id: {avg_latency_ms, avg_tokens_per_second,
    error_rate, quality_score}}`` aggregated over ``agent_executions`` from
    ``since`` until now. Model ids with no executions in the window are
    absent from the map — callers should fall back to the column on
    ``model_configs`` (typically ``None``) for those.
    """
    if not model_ids:
        return {}

    latency_expr = func.coalesce(AgentExecution.generation_latency_ms, AgentExecution.latency_ms)
    # avg_tokens_per_second: per-row tokens/sec, then averaged. NULLIF guards div-by-zero.
    tps_expr = (
        AgentExecution.total_tokens_used * 1000.0
        / func.nullif(latency_expr, 0)
    )
    # Average of (relevance + factuality) / 2 across rows where at least one of them is set.
    quality_expr = (
        (func.coalesce(AgentExecution.relevance_score, AgentExecution.factuality_score)
         + func.coalesce(AgentExecution.factuality_score, AgentExecution.relevance_score))
        / 2.0
    )

    stmt = (
        select(
            AgentExecution.model_config_id.label("model_id"),
            func.count().label("total"),
            func.sum(case((AgentExecution.status == "failed", 1), else_=0)).label("failed"),
            func.avg(latency_expr).label("avg_latency"),
            func.avg(tps_expr).label("avg_tps"),
            func.avg(quality_expr).label("avg_quality"),
        )
        .where(
            AgentExecution.tenant_id == tenant_id,
            AgentExecution.model_config_id.in_(model_ids),
            AgentExecution.created_at >= since,
        )
        .group_by(AgentExecution.model_config_id)
    )
    result: dict[uuid.UUID, dict[str, float | None]] = {}
    for row in (await db.execute(stmt)).all():
        total = int(row.total or 0)
        if not total:
            continue
        result[row.model_id] = {
            "avg_latency_ms": round(float(row.avg_latency), 2) if row.avg_latency is not None else None,
            "avg_tokens_per_second": round(float(row.avg_tps), 2) if row.avg_tps is not None else None,
            "error_rate": round(float(row.failed or 0) / total, 4),
            "quality_score": round(float(row.avg_quality), 4) if row.avg_quality is not None else None,
        }
    return result


def _select_winner(primary_metric: str, control: dict[str, float], treatment: dict[str, float]) -> str:
    metric = primary_metric or "quality_score"
    control_value = float(control.get(metric) or 0.0)
    treatment_value = float(treatment.get(metric) or 0.0)
    if metric in {"latency_ms", "error_rate"}:
        if control_value == treatment_value:
            return "inconclusive"
        return "control" if control_value < treatment_value else "treatment"
    if control_value == treatment_value:
        return "inconclusive"
    return "control" if control_value > treatment_value else "treatment"


@router.get("/deployments", response_model=list[ModelDeploymentResponse])
async def list_deployments(
    model_config_id: str = "",
    db: AsyncSession = Depends(get_read_db),
    ctx: RequestContext = Depends(get_request_context),
):
    """List model deployments."""
    query = select(ModelDeployment).where(ModelDeployment.tenant_id == ctx.tenant_id)
    if model_config_id:
        query = query.where(ModelDeployment.model_config_id == _parse_uuid(model_config_id, "model_config_id"))

    rows = (await db.scalars(query.order_by(ModelDeployment.created_at.desc()))).all()
    rows_list = list(rows)
    live_map = await _safe_live_metrics(rows_list)
    return [
        _deployment_response(row, live_metrics=live_map.get(row.id))
        for row in rows_list
    ]


@router.post("/deployments", response_model=ModelDeploymentResponse)
async def create_deployment(
    req: ModelDeploymentCreate,
    db: AsyncSession = Depends(get_write_db),
    ctx: RequestContext = Depends(get_request_context),
):
    """Create one model deployment record."""
    exists = await db.scalar(
        select(ModelConfig.id).where(
            ModelConfig.id == req.model_config_id,
            ModelConfig.tenant_id == ctx.tenant_id,
        )
    )
    if not exists:
        raise HTTPException(status_code=404, detail="model config not found")

    now = datetime.now(timezone.utc)
    row = ModelDeployment(
        id=uuid.uuid4(),
        model_config_id=req.model_config_id,
        tenant_id=ctx.tenant_id,
        deployment_name=req.deployment_name,
        deployment_type=req.deployment_type,
        endpoint_url=req.endpoint_url or None,
        replicas=req.replicas,
        gpu_type=req.gpu_type or None,
        gpu_count=req.gpu_count,
        cpu_limit=req.cpu_limit or None,
        memory_limit=req.memory_limit or None,
        status="pending",
        health_status="unknown",
        current_qps=0.0,
        max_qps=0.0,
        avg_latency_ms=0.0,
        p99_latency_ms=0.0,
        deploy_config=req.deploy_config,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    await db.flush()
    return _deployment_response(row)


@router.get("/ab-tests", response_model=list[ABTestResponse])
async def list_ab_tests(
    db: AsyncSession = Depends(get_read_db),
    ctx: RequestContext = Depends(get_request_context),
):
    """List A/B tests.

    For tests in ``running`` status, control/treatment metrics are recomputed
    live from ``agent_executions`` so the dashboard always shows the latest
    numbers — the ``control_metrics`` / ``treatment_metrics`` JSON columns
    are only finalized when a test is stopped.
    """
    rows = (
        await db.scalars(select(ABTest).where(ABTest.tenant_id == ctx.tenant_id).order_by(ABTest.created_at.desc()))
    ).all()

    responses: list[ABTestResponse] = []
    for row in rows:
        resp = _ab_test_response(row)
        if row.status == "running" and row.started_at:
            control_rows = await _model_execution_rows(
                db,
                tenant_id=ctx.tenant_id,
                model_config_id=row.control_config_id,
                since=row.started_at,
            )
            treatment_rows = await _model_execution_rows(
                db,
                tenant_id=ctx.tenant_id,
                model_config_id=row.treatment_config_id,
                since=row.started_at,
            )
            resp.control_metrics = _model_metrics_summary(control_rows)
            resp.treatment_metrics = _model_metrics_summary(treatment_rows)
        responses.append(resp)
    return responses


@router.post("/ab-tests", response_model=ABTestResponse)
async def create_ab_test(
    req: ABTestCreate,
    db: AsyncSession = Depends(get_write_db),
    ctx: RequestContext = Depends(get_request_context),
):
    """Create one A/B test."""
    now = datetime.now(timezone.utc)
    row = ABTest(
        id=uuid.uuid4(),
        tenant_id=ctx.tenant_id,
        name=req.name,
        description=req.description,
        test_type=req.test_type,
        control_config_id=req.control_config_id,
        treatment_config_id=req.treatment_config_id,
        traffic_split=req.traffic_split,
        primary_metric=req.primary_metric,
        metrics_config={},
        control_metrics={},
        treatment_metrics={},
        winner=None,
        status="draft",
        started_at=None,
        ended_at=None,
        created_at=now,
    )
    db.add(row)
    await db.flush()
    return _ab_test_response(row)


@router.post("/ab-tests/{test_id}/start")
async def start_ab_test(
    test_id: str,
    db: AsyncSession = Depends(get_write_db),
    ctx: RequestContext = Depends(get_request_context),
):
    """Start one A/B test."""
    row = await db.scalar(
        select(ABTest).where(ABTest.id == _parse_uuid(test_id, "test_id"), ABTest.tenant_id == ctx.tenant_id)
    )
    if not row:
        raise HTTPException(status_code=404, detail="ab test not found")

    row.status = "running"
    row.started_at = datetime.now(timezone.utc)
    await db.flush()
    return {"message": "ab test started"}


@router.post("/ab-tests/{test_id}/stop")
async def stop_ab_test(
    test_id: str,
    db: AsyncSession = Depends(get_write_db),
    ctx: RequestContext = Depends(get_request_context),
):
    """Stop one A/B test."""
    row = await db.scalar(
        select(ABTest).where(ABTest.id == _parse_uuid(test_id, "test_id"), ABTest.tenant_id == ctx.tenant_id)
    )
    if not row:
        raise HTTPException(status_code=404, detail="ab test not found")

    now = datetime.now(timezone.utc)
    since = row.started_at or (now - timedelta(days=7))
    control_rows = await _model_execution_rows(
        db,
        tenant_id=ctx.tenant_id,
        model_config_id=row.control_config_id,
        since=since,
    )
    treatment_rows = await _model_execution_rows(
        db,
        tenant_id=ctx.tenant_id,
        model_config_id=row.treatment_config_id,
        since=since,
    )
    row.control_metrics = _model_metrics_summary(control_rows)
    row.treatment_metrics = _model_metrics_summary(treatment_rows)
    row.winner = _select_winner(row.primary_metric, row.control_metrics, row.treatment_metrics)
    row.status = "completed"
    row.ended_at = now
    await db.flush()
    return {
        "message": "ab test stopped",
        "winner": row.winner,
        "control_metrics": row.control_metrics,
        "treatment_metrics": row.treatment_metrics,
    }


@router.get("", response_model=PageResponse[ModelConfigResponse])
async def list_model_configs(
    model_type: str = Query(default="", description="model type filter"),
    provider: str = Query(default="", description="provider filter"),
    is_active: bool | None = Query(default=None, description="active filter"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_read_db),
    ctx: RequestContext = Depends(get_request_context),
):
    """List model configs with pagination."""
    query = select(ModelConfig).where(ModelConfig.tenant_id == ctx.tenant_id)
    if model_type:
        query = query.where(ModelConfig.model_type == model_type)
    if provider:
        query = query.where(ModelConfig.provider == provider)
    if is_active is not None:
        query = query.where(ModelConfig.is_active == is_active)

    total_stmt = select(func.count()).select_from(query.subquery())
    total = int((await db.scalar(total_stmt)) or 0)

    rows = (
        await db.scalars(
            query.order_by(ModelConfig.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)
        )
    ).all()

    # Compute live performance metrics from agent_executions in the last 24h.
    # The static columns on model_configs (avg_latency_ms / error_rate / ...)
    # are never updated after row creation and would otherwise show stale 0s.
    since_24h = datetime.now(timezone.utc) - timedelta(hours=24)
    metrics_map = await _aggregate_recent_model_metrics(
        db,
        tenant_id=ctx.tenant_id,
        model_ids=[row.id for row in rows],
        since=since_24h,
    )

    return PageResponse(
        items=[_model_config_response(row, live_metrics=metrics_map.get(row.id)) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.post("", response_model=ModelConfigResponse)
async def create_model_config(
    req: ModelConfigCreate,
    db: AsyncSession = Depends(get_write_db),
    ctx: RequestContext = Depends(get_request_context),
):
    """Create one model config."""
    now = datetime.now(timezone.utc)
    row = ModelConfig(
        id=uuid.uuid4(),
        tenant_id=ctx.tenant_id,
        name=req.name,
        display_name=req.display_name,
        description=req.description or "",
        model_type=req.model_type,
        provider=req.provider,
        model_id=req.model_id,
        temperature=req.temperature,
        top_p=req.top_p,
        max_tokens=req.max_tokens,
        frequency_penalty=req.frequency_penalty,
        presence_penalty=req.presence_penalty,
        stop_sequences=req.stop_sequences,
        context_window=req.context_window,
        supports_function_calling=req.supports_function_calling,
        supports_streaming=req.supports_streaming,
        timeout_seconds=req.timeout_seconds,
        max_retries=req.max_retries,
        max_concurrent_requests=req.max_concurrent_requests,
        requests_per_minute=req.requests_per_minute,
        api_endpoint=req.api_endpoint or None,
        api_key_encrypted="***encrypted***" if req.api_key else "",
        extra_headers=req.extra_headers,
        is_active=True,
        is_default=False,
        version=1,
        avg_latency_ms=None,
        avg_tokens_per_second=None,
        error_rate=None,
        quality_score=None,
        extra_config=req.extra_config,
        created_by=ctx.user_uuid,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    await db.flush()
    return _model_config_response(row)


@router.get("/{config_id}", response_model=ModelConfigResponse)
async def get_model_config(
    config_id: str,
    db: AsyncSession = Depends(get_read_db),
    ctx: RequestContext = Depends(get_request_context),
):
    """Get one model config by id."""
    row = await db.scalar(
        select(ModelConfig).where(
            ModelConfig.id == _parse_uuid(config_id, "config_id"),
            ModelConfig.tenant_id == ctx.tenant_id,
        )
    )
    if not row:
        raise HTTPException(status_code=404, detail="model config not found")
    # Live metrics in the detail view too — keep them consistent with the list.
    since_24h = datetime.now(timezone.utc) - timedelta(hours=24)
    metrics_map = await _aggregate_recent_model_metrics(
        db,
        tenant_id=ctx.tenant_id,
        model_ids=[row.id],
        since=since_24h,
    )
    return _model_config_response(row, live_metrics=metrics_map.get(row.id))


@router.put("/{config_id}", response_model=ModelConfigResponse)
async def update_model_config(
    config_id: str,
    req: ModelConfigUpdate,
    db: AsyncSession = Depends(get_write_db),
    ctx: RequestContext = Depends(get_request_context),
):
    """Update one model config."""
    row = await db.scalar(
        select(ModelConfig).where(
            ModelConfig.id == _parse_uuid(config_id, "config_id"),
            ModelConfig.tenant_id == ctx.tenant_id,
        )
    )
    if not row:
        raise HTTPException(status_code=404, detail="model config not found")

    update_data = req.model_dump(exclude_unset=True)
    update_data.pop("api_key", None)

    for key, value in update_data.items():
        if key == "api_endpoint":
            setattr(row, key, value or None)
        else:
            setattr(row, key, value)

    row.version = (row.version or 1) + 1
    row.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return _model_config_response(row)


@router.delete("/{config_id}")
async def delete_model_config(
    config_id: str,
    db: AsyncSession = Depends(get_write_db),
    ctx: RequestContext = Depends(get_request_context),
):
    """Delete one model config."""
    row = await db.scalar(
        select(ModelConfig).where(
            ModelConfig.id == _parse_uuid(config_id, "config_id"),
            ModelConfig.tenant_id == ctx.tenant_id,
        )
    )
    if not row:
        raise HTTPException(status_code=404, detail="model config not found")

    await db.delete(row)
    await db.flush()
    return {"message": "deleted"}


@router.post("/{config_id}/toggle")
async def toggle_model_config(
    config_id: str,
    db: AsyncSession = Depends(get_write_db),
    ctx: RequestContext = Depends(get_request_context),
):
    """Toggle one model config active flag."""
    row = await db.scalar(
        select(ModelConfig).where(
            ModelConfig.id == _parse_uuid(config_id, "config_id"),
            ModelConfig.tenant_id == ctx.tenant_id,
        )
    )
    if not row:
        raise HTTPException(status_code=404, detail="model config not found")

    row.is_active = not bool(row.is_active)
    row.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return {"is_active": row.is_active}


@router.post("/{config_id}/set-default")
async def set_default_model(
    config_id: str,
    db: AsyncSession = Depends(get_write_db),
    ctx: RequestContext = Depends(get_request_context),
):
    """Set one model config as default for its model type."""
    row = await db.scalar(
        select(ModelConfig).where(
            ModelConfig.id == _parse_uuid(config_id, "config_id"),
            ModelConfig.tenant_id == ctx.tenant_id,
        )
    )
    if not row:
        raise HTTPException(status_code=404, detail="model config not found")

    now = datetime.now(timezone.utc)
    await db.execute(
        update(ModelConfig)
        .where(
            ModelConfig.tenant_id == ctx.tenant_id,
            ModelConfig.model_type == row.model_type,
        )
        .values(is_default=False, updated_at=now)
    )
    row.is_default = True
    row.updated_at = now
    await db.flush()
    return {"message": "set as default"}


@router.get("/{config_id}/metrics")
async def get_model_metrics_compat(
    config_id: str,
    response: Response,
    period: str = "24h",
    db: AsyncSession = Depends(get_read_db),
    ctx: RequestContext = Depends(get_request_context),
):
    """Compatibility endpoint for legacy `/models/{id}/metrics`."""
    row = await db.scalar(
        select(ModelConfig).where(
            ModelConfig.id == _parse_uuid(config_id, "config_id"),
            ModelConfig.tenant_id == ctx.tenant_id,
        )
    )
    if not row:
        raise HTTPException(status_code=404, detail="model config not found")

    _set_compat_headers(response, "/api/v1/models/deployments")

    since, bucket_count = _period_window(period)
    rows = await _model_execution_rows(
        db,
        tenant_id=ctx.tenant_id,
        model_config_id=row.id,
        since=since,
    )
    payload = _model_metrics_timeseries(rows, since=since, bucket_count=bucket_count)
    payload["sample_count"] = len(rows)
    payload["source"] = "agent_executions"
    return payload


@router.post("/{config_id}/deploy")
async def deploy_model_compat(
    config_id: str,
    response: Response,
    config: dict[str, Any] | None = None,
    db: AsyncSession = Depends(get_write_db),
    ctx: RequestContext = Depends(get_request_context),
):
    """Compatibility endpoint for legacy `/models/{id}/deploy`."""
    model = await db.scalar(
        select(ModelConfig).where(
            ModelConfig.id == _parse_uuid(config_id, "config_id"),
            ModelConfig.tenant_id == ctx.tenant_id,
        )
    )
    if not model:
        raise HTTPException(status_code=404, detail="model config not found")

    payload = config or {}
    now = datetime.now(timezone.utc)
    deployment = ModelDeployment(
        id=uuid.uuid4(),
        model_config_id=model.id,
        tenant_id=ctx.tenant_id,
        deployment_name=payload.get("deployment_name") or f"{model.name}-deployment",
        deployment_type=payload.get("deployment_type") or "cloud_api",
        endpoint_url=payload.get("endpoint_url"),
        replicas=int(payload.get("replicas") or 1),
        gpu_type=payload.get("gpu_type"),
        gpu_count=int(payload.get("gpu_count") or 0),
        cpu_limit=payload.get("cpu_limit"),
        memory_limit=payload.get("memory_limit"),
        status="pending",
        health_status="unknown",
        current_qps=0.0,
        max_qps=float(payload.get("max_qps") or 0.0),
        avg_latency_ms=0.0,
        p99_latency_ms=0.0,
        deploy_config=payload,
        created_at=now,
        updated_at=now,
    )
    db.add(deployment)
    await db.flush()

    _set_compat_headers(response, "/api/v1/models/deployments")

    live_map = await _safe_live_metrics([deployment])
    live = live_map.get(deployment.id) or DeploymentLiveMetrics()

    if live.ready_replicas is not None:
        ready_replicas = live.ready_replicas
    else:
        ready_replicas = (
            deployment.replicas
            if deployment.status == "running" and deployment.health_status == "healthy"
            else 0
        )

    return {
        "id": str(deployment.id),
        "model_id": str(model.id),
        "model_name": model.display_name,
        "status": deployment.status,
        "gpu_type": deployment.gpu_type or "",
        "gpu_count": deployment.gpu_count,
        "replicas": deployment.replicas,
        "ready_replicas": ready_replicas,
        "cpu_usage": live.cpu_usage,
        "memory_usage": live.memory_usage,
        "current_qps": live.current_qps if live.current_qps is not None else deployment.current_qps,
        "p99_latency_ms": live.p99_latency_ms if live.p99_latency_ms is not None else deployment.p99_latency_ms,
        "created_at": deployment.created_at.isoformat(),
    }


@router.post("/{config_id}/undeploy")
async def undeploy_model_compat(
    config_id: str,
    response: Response,
    db: AsyncSession = Depends(get_write_db),
    ctx: RequestContext = Depends(get_request_context),
):
    """Compatibility endpoint for legacy `/models/{id}/undeploy`."""
    config_uuid = _parse_uuid(config_id, "config_id")
    now = datetime.now(timezone.utc)
    result = await db.execute(
        update(ModelDeployment)
        .where(
            ModelDeployment.model_config_id == config_uuid,
            ModelDeployment.tenant_id == ctx.tenant_id,
        )
        .values(status="stopped", health_status="unknown", updated_at=now)
    )
    await db.flush()

    _set_compat_headers(response, "/api/v1/models/deployments")

    return {"message": "undeployed", "updated": int(getattr(result, "rowcount", 0) or 0)}
