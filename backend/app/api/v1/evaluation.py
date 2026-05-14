"""Evaluation APIs: LLM-as-judge scoring and quality metrics."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_read_db, get_write_db
from app.core.request_context import RequestContext, resolve_request_context
from app.services.evaluation_service import evaluation_service

from fastapi import Request

router = APIRouter()


def get_request_context(request: Request) -> RequestContext:
    return resolve_request_context(request)


@router.post("/score/{execution_id}")
async def score_execution(
    execution_id: str,
    db: AsyncSession = Depends(get_write_db),
    ctx: RequestContext = Depends(get_request_context),
):
    import uuid
    return await evaluation_service.score_execution(db, uuid.UUID(execution_id), ctx.tenant_id)


@router.post("/batch")
async def batch_score(
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_write_db),
    ctx: RequestContext = Depends(get_request_context),
):
    return await evaluation_service.batch_score(db, ctx.tenant_id, limit=limit)


@router.get("/metrics")
async def get_eval_metrics(
    db: AsyncSession = Depends(get_read_db),
    ctx: RequestContext = Depends(get_request_context),
):
    return await evaluation_service.get_metrics(db, ctx.tenant_id)
