"""Ingestion job schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class IngestionJobResponse(BaseModel):
    job_id: UUID
    tenant_id: str
    status: str
    stage: str
    file_name: str
    doc_id: UUID | None
    doc_type: str | None
    title: str | None
    attempt_count: int
    error_message: str | None
    result: dict = Field(default_factory=dict)
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    updated_at: datetime


class IngestionStageEventResponse(BaseModel):
    stage: str
    status: str
    detail: dict = Field(default_factory=dict)
    created_at: datetime


class ChunkIndexState(BaseModel):
    chunk_id: UUID
    vector_status: str
    graph_status: str
