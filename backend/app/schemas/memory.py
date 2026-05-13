"""Memory API schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class MemoryFactResponse(BaseModel):
    id: UUID
    fact_key: str
    fact_value: str
    confidence: float
    tags: list[str] = Field(default_factory=list)
    updated_at: datetime


class MemorySummaryResponse(BaseModel):
    id: UUID
    summary_type: str
    content: str
    token_count: int
    window_start_index: int
    window_end_index: int
    updated_at: datetime


class SessionMemoryResponse(BaseModel):
    session_id: UUID
    tenant_id: str
    facts: list[MemoryFactResponse] = Field(default_factory=list)
    summaries: list[MemorySummaryResponse] = Field(default_factory=list)
