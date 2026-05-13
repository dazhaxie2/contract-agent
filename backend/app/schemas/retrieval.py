"""Retrieval debug API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class RetrievalSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=10000)
    session_id: UUID | None = None
    tenant_id: str | None = None
    filters: dict = Field(default_factory=dict)
    top_k: int = Field(default=10, ge=1, le=50)


class RetrievalHit(BaseModel):
    chunk_id: str
    content: str
    score: float
    source: str
    metadata: dict = Field(default_factory=dict)
    rerank_score: float | None = None
    citation_id: UUID | None = None
    citation_code: str | None = None


class RetrievalDebugResponse(BaseModel):
    query: str
    retrieval_id: UUID
    latency_ms: float
    preprocessed: dict = Field(default_factory=dict)
    channels: dict = Field(default_factory=dict)
    merged: list[dict[str, Any]] = Field(default_factory=list)
    reranked: list[dict[str, Any]] = Field(default_factory=list)
    filtered_out: list[dict[str, Any]] = Field(default_factory=list)
    final_results: list[RetrievalHit] = Field(default_factory=list)
    context: str
    references: list[dict] = Field(default_factory=list)
    created_at: datetime
