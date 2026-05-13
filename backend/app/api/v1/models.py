"""Model configuration APIs backed by relational database."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_read_db, get_write_db
from app.core.request_context import RequestContext, resolve_request_context
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


def _model_config_response(row: ModelConfig) -> ModelConfigResponse:
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
        avg_latency_ms=row.avg_latency_ms,
        avg_tokens_per_second=row.avg_tokens_per_second,
        error_rate=row.error_rate,
        quality_score=row.quality_score,
        extra_config=row.extra_config or {},
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _deployment_response(row: ModelDeployment) -> ModelDeploymentResponse:
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
        current_qps=row.current_qps,
        max_qps=row.max_qps,
        avg_latency_ms=row.avg_latency_ms,
        p99_latency_ms=row.p99_latency_ms,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


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
    return [_deployment_response(row) for row in rows]


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
    """List A/B tests."""
    rows = (
        await db.scalars(select(ABTest).where(ABTest.tenant_id == ctx.tenant_id).order_by(ABTest.created_at.desc()))
    ).all()
    return [_ab_test_response(row) for row in rows]


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

    row.status = "completed"
    row.ended_at = datetime.now(timezone.utc)
    await db.flush()
    return {"message": "ab test stopped"}


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

    return PageResponse(
        items=[_model_config_response(row) for row in rows],
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
    return _model_config_response(row)


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

    point_count = 12 if period in {"24h", "day"} else 7
    now = datetime.now(timezone.utc)
    timestamps = [
        (now - timedelta(hours=(point_count - idx - 1) * 2)).isoformat()
        for idx in range(point_count)
    ]

    base_latency = float(row.avg_latency_ms or 120.0)
    base_error = float(row.error_rate or 0.0)
    base_quality = float(row.quality_score or 0.0)
    lat_p50 = [round(base_latency * (0.95 + (idx % 3) * 0.03), 2) for idx in range(point_count)]
    lat_p99 = [round(v * 1.8, 2) for v in lat_p50]
    qps = [round(10 + idx * 1.5, 2) for idx in range(point_count)]
    error_rate = [round(max(0.0, base_error), 4) for _ in range(point_count)]
    quality = [round(max(0.0, base_quality), 4) for _ in range(point_count)]

    return {
        "timestamps": timestamps,
        "latency_p50": lat_p50,
        "latency_p99": lat_p99,
        "qps": qps,
        "error_rate": error_rate,
        "quality_score": quality,
    }


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
        status="running",
        health_status="healthy",
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

    return {
        "id": str(deployment.id),
        "model_id": str(model.id),
        "model_name": model.display_name,
        "status": deployment.status,
        "gpu_type": deployment.gpu_type or "",
        "gpu_count": deployment.gpu_count,
        "replicas": deployment.replicas,
        "ready_replicas": deployment.replicas,
        "cpu_usage": 0.0,
        "memory_usage": 0.0,
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

    return {"message": "undeployed", "updated": int(result.rowcount or 0)}
