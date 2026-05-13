"""Citation API schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CitationResponse(BaseModel):
    id: UUID
    citation_code: str
    tenant_id: str
    session_id: UUID | None
    execution_id: UUID | None
    document_id: UUID | None
    chunk_id: UUID | None
    source_type: str
    title: str | None
    excerpt: str
    locator: str | None
    metadata: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
