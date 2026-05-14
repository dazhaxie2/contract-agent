"""Prompt template APIs backed by relational database."""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_read_db, get_write_db
from app.core.request_context import RequestContext, resolve_request_context
from app.models.prompt import PromptTemplate, PromptVersion
from app.schemas.common import PageResponse
from app.schemas.prompt import (
    PromptTemplateCreate,
    PromptTemplateResponse,
    PromptTemplateUpdate,
    PromptTestRequest,
    PromptTestResponse,
    PromptVersionResponse,
)
from app.services.llm_service import llm_service

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


def _normalize_variables(variables: list) -> list[dict]:
    normalized: list[dict] = []
    for var in variables:
        if hasattr(var, "model_dump"):
            normalized.append(var.model_dump())
        elif isinstance(var, dict):
            normalized.append(var)
        else:
            normalized.append({"name": str(var)})
    return normalized


def _prompt_template_response(row: PromptTemplate) -> PromptTemplateResponse:
    return PromptTemplateResponse(
        id=row.id,
        name=row.name,
        display_name=row.display_name,
        description=row.description or "",
        category=row.category,
        task_type=row.task_type,
        system_prompt=row.system_prompt,
        user_prompt_template=row.user_prompt_template,
        variables=row.variables or [],
        target_model_type=row.target_model_type,
        target_agent=row.target_agent,
        output_format=row.output_format,
        output_schema=row.output_schema,
        validation_rules=row.validation_rules or [],
        current_version=row.current_version,
        status=row.status,
        is_default=row.is_default,
        tags=row.tags or [],
        avg_quality_score=row.avg_quality_score,
        usage_count=row.usage_count,
        created_at=row.created_at,
        updated_at=row.updated_at,
        published_at=row.published_at,
    )


def _prompt_version_response(row: PromptVersion) -> PromptVersionResponse:
    return PromptVersionResponse(
        id=row.id,
        template_id=row.template_id,
        version=row.version,
        system_prompt=row.system_prompt,
        user_prompt_template=row.user_prompt_template,
        variables=row.variables or [],
        output_format=row.output_format,
        changelog=row.changelog,
        quality_score=row.quality_score,
        evaluation_results=row.evaluation_results or {},
        created_at=row.created_at,
    )


async def _run_prompt_test(req: PromptTestRequest, db: AsyncSession, tenant_id: str) -> PromptTestResponse:
    system_prompt = req.system_prompt
    user_prompt_template = req.user_prompt_template

    if req.template_id:
        tpl = await db.scalar(
            select(PromptTemplate).where(
                PromptTemplate.id == req.template_id,
                PromptTemplate.tenant_id == tenant_id,
            )
        )
        if not tpl:
            raise HTTPException(status_code=404, detail="prompt template not found")
        system_prompt = tpl.system_prompt or system_prompt
        user_prompt_template = tpl.user_prompt_template or user_prompt_template

    rendered = user_prompt_template
    for var_name, var_value in req.variables.items():
        rendered = rendered.replace(f"{{{{{var_name}}}}}", str(var_value))

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": rendered})

    start_time = time.perf_counter()
    result = await llm_service.generate(
        messages=messages,
        temperature=req.temperature,
        max_tokens=req.max_tokens,
    )
    latency_ms = (time.perf_counter() - start_time) * 1000

    return PromptTestResponse(
        trace_id=f"prompt_{uuid.uuid4().hex[:24]}",
        rendered_prompt=rendered,
        output=result["content"],
        model=result.get("model", ""),
        usage=result.get("usage", {}),
        latency_ms=round(latency_ms, 2),
    )


@router.post("/test", response_model=PromptTestResponse)
async def test_prompt(
    req: PromptTestRequest,
    db: AsyncSession = Depends(get_read_db),
    ctx: RequestContext = Depends(get_request_context),
):
    """Render and test prompt output with current model service."""
    return await _run_prompt_test(req, db, ctx.tenant_id)


@router.post("/{template_id}/test")
async def test_prompt_compat(
    template_id: str,
    response: Response,
    payload: dict[str, Any] | None = None,
    db: AsyncSession = Depends(get_read_db),
    ctx: RequestContext = Depends(get_request_context),
):
    """Compatibility endpoint for legacy `/prompts/{id}/test`."""
    body = payload or {}
    req = PromptTestRequest(
        template_id=_parse_uuid(template_id, "template_id"),
        system_prompt=body.get("system_prompt", ""),
        user_prompt_template=body.get("user_prompt_template", ""),
        variables=body.get("variables", {}),
        model_config_id=body.get("model_config_id"),
        temperature=body.get("temperature"),
        max_tokens=body.get("max_tokens"),
    )
    result = await _run_prompt_test(req, db, ctx.tenant_id)
    _set_compat_headers(response, "/api/v1/prompts/test")
    usage = result.usage or {}
    return {
        "trace_id": result.trace_id,
        "rendered_prompt": result.rendered_prompt,
        "output": result.output,
        "tokens_used": usage.get("total_tokens", 0),
        "latency_ms": result.latency_ms,
        "score": result.quality_score or 0,
        "model_used": result.model,
    }


@router.get("", response_model=PageResponse[PromptTemplateResponse])
async def list_prompts(
    category: str = Query(default="", description="category filter"),
    task_type: str = Query(default="", description="task type filter"),
    status: str = Query(default="", description="status filter"),
    target_agent: str = Query(default="", description="target agent filter"),
    search: str = Query(default="", description="keyword search"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_read_db),
    ctx: RequestContext = Depends(get_request_context),
):
    """List prompt templates with pagination."""
    query = select(PromptTemplate).where(PromptTemplate.tenant_id == ctx.tenant_id)

    if category:
        query = query.where(PromptTemplate.category == category)
    if task_type:
        query = query.where(PromptTemplate.task_type == task_type)
    if status:
        query = query.where(PromptTemplate.status == status)
    if target_agent:
        query = query.where(PromptTemplate.target_agent == target_agent)
    if search:
        query = query.where(
            PromptTemplate.name.ilike(f"%{search}%") | PromptTemplate.display_name.ilike(f"%{search}%")
        )

    total_stmt = select(func.count()).select_from(query.subquery())
    total = int((await db.scalar(total_stmt)) or 0)

    rows = (
        await db.scalars(
            query.order_by(PromptTemplate.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)
        )
    ).all()

    return PageResponse(
        items=[_prompt_template_response(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.post("", response_model=PromptTemplateResponse)
async def create_prompt(
    req: PromptTemplateCreate,
    db: AsyncSession = Depends(get_write_db),
    ctx: RequestContext = Depends(get_request_context),
):
    """Create prompt template and initial version snapshot."""
    now = datetime.now(timezone.utc)
    tpl_id = uuid.uuid4()
    variables = _normalize_variables(req.variables)

    tpl = PromptTemplate(
        id=tpl_id,
        tenant_id=ctx.tenant_id,
        name=req.name,
        display_name=req.display_name,
        description=req.description or "",
        category=req.category,
        task_type=req.task_type or None,
        system_prompt=req.system_prompt or None,
        user_prompt_template=req.user_prompt_template,
        variables=variables,
        target_model_type=req.target_model_type or None,
        target_agent=req.target_agent or None,
        output_format=req.output_format or "text",
        output_schema=req.output_schema,
        validation_rules=req.validation_rules,
        current_version=1,
        status="draft",
        is_default=False,
        tags=req.tags,
        avg_quality_score=None,
        usage_count=0,
        created_by=ctx.user_uuid,
        published_by=None,
        created_at=now,
        updated_at=now,
        published_at=None,
    )
    db.add(tpl)

    version = PromptVersion(
        id=uuid.uuid4(),
        template_id=tpl_id,
        tenant_id=ctx.tenant_id,
        version=1,
        system_prompt=tpl.system_prompt,
        user_prompt_template=tpl.user_prompt_template,
        variables=variables,
        output_format=tpl.output_format,
        output_schema=tpl.output_schema,
        validation_rules=tpl.validation_rules,
        changelog="initial version",
        evaluation_results={},
        quality_score=None,
        created_by=ctx.user_uuid,
        created_at=now,
    )
    db.add(version)
    await db.flush()
    return _prompt_template_response(tpl)


@router.get("/{template_id}", response_model=PromptTemplateResponse)
async def get_prompt(
    template_id: str,
    db: AsyncSession = Depends(get_read_db),
    ctx: RequestContext = Depends(get_request_context),
):
    """Get one prompt template detail."""
    tpl = await db.scalar(
        select(PromptTemplate).where(
            PromptTemplate.id == _parse_uuid(template_id, "template_id"),
            PromptTemplate.tenant_id == ctx.tenant_id,
        )
    )
    if not tpl:
        raise HTTPException(status_code=404, detail="prompt template not found")
    return _prompt_template_response(tpl)


@router.put("/{template_id}", response_model=PromptTemplateResponse)
async def update_prompt(
    template_id: str,
    req: PromptTemplateUpdate,
    db: AsyncSession = Depends(get_write_db),
    ctx: RequestContext = Depends(get_request_context),
):
    """Update prompt template and create one new version snapshot."""
    tpl = await db.scalar(
        select(PromptTemplate).where(
            PromptTemplate.id == _parse_uuid(template_id, "template_id"),
            PromptTemplate.tenant_id == ctx.tenant_id,
        )
    )
    if not tpl:
        raise HTTPException(status_code=404, detail="prompt template not found")

    update_data = req.model_dump(exclude_unset=True)
    changelog = update_data.pop("changelog", "")

    if "variables" in update_data and update_data["variables"] is not None:
        update_data["variables"] = _normalize_variables(update_data["variables"])

    for key, value in update_data.items():
        if key in {"task_type", "system_prompt", "target_model_type", "target_agent"}:
            setattr(tpl, key, value or None)
        else:
            setattr(tpl, key, value)

    now = datetime.now(timezone.utc)
    tpl.current_version = (tpl.current_version or 1) + 1
    tpl.updated_at = now

    version = PromptVersion(
        id=uuid.uuid4(),
        template_id=tpl.id,
        tenant_id=tpl.tenant_id,
        version=tpl.current_version,
        system_prompt=tpl.system_prompt,
        user_prompt_template=tpl.user_prompt_template,
        variables=tpl.variables or [],
        output_format=tpl.output_format,
        output_schema=tpl.output_schema,
        validation_rules=tpl.validation_rules or [],
        changelog=changelog,
        evaluation_results={},
        quality_score=None,
        created_by=ctx.user_uuid,
        created_at=now,
    )
    db.add(version)
    await db.flush()
    return _prompt_template_response(tpl)


@router.post("/{template_id}/publish")
async def publish_prompt(
    template_id: str,
    db: AsyncSession = Depends(get_write_db),
    ctx: RequestContext = Depends(get_request_context),
):
    """Publish one prompt template."""
    tpl = await db.scalar(
        select(PromptTemplate).where(
            PromptTemplate.id == _parse_uuid(template_id, "template_id"),
            PromptTemplate.tenant_id == ctx.tenant_id,
        )
    )
    if not tpl:
        raise HTTPException(status_code=404, detail="prompt template not found")

    now = datetime.now(timezone.utc)
    tpl.status = "published"
    tpl.published_by = ctx.user_uuid
    tpl.published_at = now
    tpl.updated_at = now
    await db.flush()
    return {"message": "published", "version": tpl.current_version}


@router.post("/{template_id}/deprecate")
async def deprecate_prompt(
    template_id: str,
    db: AsyncSession = Depends(get_write_db),
    ctx: RequestContext = Depends(get_request_context),
):
    """Deprecate one prompt template."""
    tpl = await db.scalar(
        select(PromptTemplate).where(
            PromptTemplate.id == _parse_uuid(template_id, "template_id"),
            PromptTemplate.tenant_id == ctx.tenant_id,
        )
    )
    if not tpl:
        raise HTTPException(status_code=404, detail="prompt template not found")

    tpl.status = "deprecated"
    tpl.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return {"message": "deprecated"}


@router.get("/{template_id}/versions", response_model=list[PromptVersionResponse])
async def list_prompt_versions(
    template_id: str,
    db: AsyncSession = Depends(get_read_db),
    ctx: RequestContext = Depends(get_request_context),
):
    """List all versions of one prompt template."""
    template_uuid = _parse_uuid(template_id, "template_id")
    rows = (
        await db.scalars(
            select(PromptVersion)
            .where(
                PromptVersion.template_id == template_uuid,
                PromptVersion.tenant_id == ctx.tenant_id,
            )
            .order_by(PromptVersion.version.desc())
        )
    ).all()
    return [_prompt_version_response(row) for row in rows]


@router.get("/{template_id}/versions/{version}", response_model=PromptVersionResponse)
async def get_prompt_version(
    template_id: str,
    version: int,
    db: AsyncSession = Depends(get_read_db),
    ctx: RequestContext = Depends(get_request_context),
):
    """Get one specific prompt version."""
    row = await db.scalar(
        select(PromptVersion).where(
            PromptVersion.template_id == _parse_uuid(template_id, "template_id"),
            PromptVersion.version == version,
            PromptVersion.tenant_id == ctx.tenant_id,
        )
    )
    if not row:
        raise HTTPException(status_code=404, detail=f"version {version} not found")
    return _prompt_version_response(row)


@router.post("/{template_id}/versions/{version}/rollback")
async def rollback_prompt(
    template_id: str,
    version: int,
    db: AsyncSession = Depends(get_write_db),
    ctx: RequestContext = Depends(get_request_context),
):
    """Rollback template to a previous version and create new snapshot."""
    template_uuid = _parse_uuid(template_id, "template_id")
    tpl = await db.scalar(
        select(PromptTemplate).where(
            PromptTemplate.id == template_uuid,
            PromptTemplate.tenant_id == ctx.tenant_id,
        )
    )
    if not tpl:
        raise HTTPException(status_code=404, detail="prompt template not found")

    target = await db.scalar(
        select(PromptVersion).where(
            PromptVersion.template_id == template_uuid,
            PromptVersion.version == version,
            PromptVersion.tenant_id == ctx.tenant_id,
        )
    )
    if not target:
        raise HTTPException(status_code=404, detail=f"version {version} not found")

    tpl.system_prompt = target.system_prompt
    tpl.user_prompt_template = target.user_prompt_template
    tpl.variables = target.variables or []
    tpl.output_format = target.output_format
    tpl.output_schema = target.output_schema
    tpl.validation_rules = target.validation_rules or []

    now = datetime.now(timezone.utc)
    tpl.current_version = (tpl.current_version or 1) + 1
    tpl.updated_at = now

    rollback_snapshot = PromptVersion(
        id=uuid.uuid4(),
        template_id=template_uuid,
        tenant_id=ctx.tenant_id,
        version=tpl.current_version,
        system_prompt=tpl.system_prompt,
        user_prompt_template=tpl.user_prompt_template,
        variables=tpl.variables or [],
        output_format=tpl.output_format,
        output_schema=tpl.output_schema,
        validation_rules=tpl.validation_rules or [],
        changelog=f"rollback to version {version}",
        evaluation_results={},
        quality_score=None,
        created_by=ctx.user_uuid,
        created_at=now,
    )
    db.add(rollback_snapshot)
    await db.flush()

    return {"message": f"rolled back to version {version}", "new_version": tpl.current_version}
