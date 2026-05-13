"""Session memory APIs."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_read_db, get_write_db
from app.core.request_context import RequestContext, resolve_request_context
from app.models.memory import MemoryFact, MemorySummary
from app.schemas.memory import MemoryFactResponse, MemorySummaryResponse, SessionMemoryResponse
from app.services.session_memory_service import session_memory_service

router = APIRouter()


def get_request_context(request: Request) -> RequestContext:
    return resolve_request_context(request)


def _parse_uuid(value: str, field_name: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"invalid {field_name}") from exc


@router.get("/{session_id}", response_model=SessionMemoryResponse)
async def get_memory(
    session_id: str,
    db: AsyncSession = Depends(get_read_db),
    ctx: RequestContext = Depends(get_request_context),
):
    session_uuid = _parse_uuid(session_id, "session_id")
    session = await session_memory_service.get_session(db, session_uuid, ctx.tenant_id)
    if not session:
        raise HTTPException(status_code=404, detail="session not found")

    facts = (
        await db.scalars(
            select(MemoryFact)
            .where(MemoryFact.session_id == session_uuid, MemoryFact.tenant_id == ctx.tenant_id)
            .order_by(MemoryFact.updated_at.desc())
        )
    ).all()
    summaries = (
        await db.scalars(
            select(MemorySummary)
            .where(MemorySummary.session_id == session_uuid, MemorySummary.tenant_id == ctx.tenant_id)
            .order_by(MemorySummary.updated_at.desc())
        )
    ).all()

    return SessionMemoryResponse(
        session_id=session_uuid,
        tenant_id=ctx.tenant_id,
        facts=[
            MemoryFactResponse(
                id=f.id,
                fact_key=f.fact_key,
                fact_value=f.fact_value,
                confidence=float(f.confidence or 0.0),
                tags=f.tags or [],
                updated_at=f.updated_at,
            )
            for f in facts
        ],
        summaries=[
            MemorySummaryResponse(
                id=s.id,
                summary_type=s.summary_type,
                content=s.content,
                token_count=s.token_count,
                window_start_index=s.window_start_index,
                window_end_index=s.window_end_index,
                updated_at=s.updated_at,
            )
            for s in summaries
        ],
    )


@router.post("/rebuild/{session_id}")
async def rebuild_memory(
    session_id: str,
    db: AsyncSession = Depends(get_write_db),
    ctx: RequestContext = Depends(get_request_context),
):
    session_uuid = _parse_uuid(session_id, "session_id")
    session = await session_memory_service.get_session(db, session_uuid, ctx.tenant_id)
    if not session:
        raise HTTPException(status_code=404, detail="session not found")

    rebuilt = await session_memory_service.rebuild_session_memory(
        db=db,
        session_id=session_uuid,
        tenant_id=ctx.tenant_id,
    )
    return {"session_id": session_uuid, "tenant_id": ctx.tenant_id, "rebuild": rebuilt}
