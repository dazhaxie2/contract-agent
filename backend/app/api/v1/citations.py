"""Citation lookup API."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_read_db
from app.core.request_context import RequestContext, resolve_request_context
from app.models.retrieval import CitationRecord
from app.schemas.citation import CitationResponse

router = APIRouter()


def get_request_context(request: Request) -> RequestContext:
    return resolve_request_context(request)


def _parse_uuid(value: str, field_name: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"invalid {field_name}") from exc


@router.get("/{citation_id}", response_model=CitationResponse)
async def get_citation(
    citation_id: str,
    db: AsyncSession = Depends(get_read_db),
    ctx: RequestContext = Depends(get_request_context),
):
    citation_uuid = _parse_uuid(citation_id, "citation_id")
    row = await db.scalar(
        select(CitationRecord).where(
            CitationRecord.id == citation_uuid,
            CitationRecord.tenant_id == ctx.tenant_id,
        )
    )
    if not row:
        raise HTTPException(status_code=404, detail="citation not found")

    return CitationResponse(
        id=row.id,
        citation_code=row.citation_code,
        tenant_id=row.tenant_id,
        session_id=row.session_id,
        execution_id=row.execution_id,
        document_id=row.document_id,
        chunk_id=row.chunk_id,
        source_type=row.source_type,
        title=row.title,
        excerpt=row.excerpt,
        locator=row.locator,
        metadata=row.metadata_extra or {},
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
