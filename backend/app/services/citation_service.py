"""Citation record creation and lookup helpers."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.retrieval import CitationRecord


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_uuid(value: Any) -> uuid.UUID | None:
    if isinstance(value, uuid.UUID):
        return value
    if isinstance(value, str):
        try:
            return uuid.UUID(value)
        except ValueError:
            return None
    return None


def _new_citation_code() -> str:
    return f"CIT-{uuid.uuid4().hex[:12].upper()}"


class CitationService:
    async def ensure_for_result(
        self,
        db: AsyncSession,
        *,
        tenant_id: str,
        chunk_id: str | uuid.UUID | None,
        excerpt: str,
        title: str | None,
        locator: str | None,
        metadata: dict | None = None,
        session_id: uuid.UUID | None = None,
        execution_id: uuid.UUID | None = None,
        document_id: str | uuid.UUID | None = None,
    ) -> CitationRecord:
        chunk_uuid = _parse_uuid(chunk_id)
        document_uuid = _parse_uuid(document_id)

        existing = None
        if chunk_uuid:
            existing = await db.scalar(
                select(CitationRecord).where(
                    CitationRecord.tenant_id == tenant_id,
                    CitationRecord.chunk_id == chunk_uuid,
                )
            )
        if existing:
            existing.excerpt = excerpt
            existing.title = title
            existing.locator = locator
            existing.metadata_extra = metadata or {}
            existing.session_id = session_id
            existing.execution_id = execution_id
            existing.document_id = document_uuid
            existing.updated_at = _utcnow()
            await db.flush()
            return existing

        row = CitationRecord(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            session_id=session_id,
            execution_id=execution_id,
            document_id=document_uuid,
            chunk_id=chunk_uuid,
            citation_code=_new_citation_code(),
            source_type="document_chunk",
            title=title,
            excerpt=excerpt,
            locator=locator,
            metadata_extra=metadata or {},
            created_at=_utcnow(),
            updated_at=_utcnow(),
        )
        db.add(row)
        await db.flush()
        return row


citation_service = CitationService()
