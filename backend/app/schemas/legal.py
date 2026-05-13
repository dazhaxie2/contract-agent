"""Schemas for legal source synchronization."""

from __future__ import annotations

from pydantic import BaseModel, Field


class LegalSyncRequest(BaseModel):
    tenant_id: str | None = None
    limit: int | None = Field(default=None, ge=1, le=500)


class LegalSyncResponse(BaseModel):
    tenant_id: str
    total: int
    enqueued: int
    skipped: int
    failed: int
    job_ids: list[str] = Field(default_factory=list)

