"""Session and history APIs."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_read_db, get_write_db
from app.core.request_context import RequestContext, resolve_request_context
from app.schemas.session import ConversationMessageResponse, SessionCreateRequest, SessionResponse
from app.services.session_memory_service import session_memory_service

router = APIRouter()


def get_request_context(request: Request) -> RequestContext:
    return resolve_request_context(request)


def _parse_uuid(value: str, field_name: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"invalid {field_name}") from exc


def _session_payload(row) -> SessionResponse:
    return SessionResponse(
        id=row.id,
        tenant_id=row.tenant_id,
        user_id=row.user_id,
        title=row.title,
        status=row.status,
        metadata=row.metadata_extra or {},
        last_message_at=row.last_message_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _message_payload(row) -> ConversationMessageResponse:
    return ConversationMessageResponse(
        id=row.id,
        session_id=row.session_id,
        role=row.role,
        content=row.content,
        token_count=row.token_count,
        message_index=row.message_index,
        trace_id=row.trace_id,
        metadata=row.metadata_extra or {},
        created_at=row.created_at,
    )


@router.post("", response_model=SessionResponse)
async def create_session(
    req: SessionCreateRequest,
    db: AsyncSession = Depends(get_write_db),
    ctx: RequestContext = Depends(get_request_context),
):
    session_id = uuid.uuid4()
    row = await session_memory_service.ensure_session(
        db=db,
        session_id=session_id,
        tenant_id=ctx.tenant_id,
        user_id=ctx.user_uuid,
        title=req.title,
    )
    row.metadata_extra = req.metadata
    await db.flush()
    return _session_payload(row)


@router.get("")
async def list_sessions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_read_db),
    ctx: RequestContext = Depends(get_request_context),
):
    rows, total = await session_memory_service.list_sessions(
        db=db,
        tenant_id=ctx.tenant_id,
        user_id=ctx.user_uuid,
        page=page,
        page_size=page_size,
    )
    return {
        "items": [_session_payload(row).model_dump() for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_read_db),
    ctx: RequestContext = Depends(get_request_context),
):
    session_uuid = _parse_uuid(session_id, "session_id")
    row = await session_memory_service.get_session(db, session_uuid, ctx.tenant_id)
    if not row:
        raise HTTPException(status_code=404, detail="session not found")
    return _session_payload(row)


@router.get("/{session_id}/messages")
async def get_session_messages(
    session_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_read_db),
    ctx: RequestContext = Depends(get_request_context),
):
    session_uuid = _parse_uuid(session_id, "session_id")
    row = await session_memory_service.get_session(db, session_uuid, ctx.tenant_id)
    if not row:
        raise HTTPException(status_code=404, detail="session not found")
    messages, total = await session_memory_service.list_messages(
        db=db,
        session_id=session_uuid,
        tenant_id=ctx.tenant_id,
        page=page,
        page_size=page_size,
    )
    return {
        "items": [_message_payload(msg).model_dump() for msg in messages],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }
