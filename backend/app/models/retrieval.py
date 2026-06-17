"""Retrieval logs and citation records."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, Index, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RetrievalLog(Base):
    __tablename__ = "retrieval_logs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    session_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=True, index=True)
    execution_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=True, index=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    filters: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    preprocessed: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    vector_hits: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    keyword_hits: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    graph_hits: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    merged_hits: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    rerank_scores: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    filtered_out: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    final_context: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("idx_retrieval_tenant_time", "tenant_id", "created_at"),
        Index("idx_retrieval_session_time", "session_id", "created_at"),
    )


class CitationRecord(Base):
    __tablename__ = "citation_records"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    session_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True, index=True)
    execution_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True, index=True)
    document_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True, index=True)
    chunk_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True, index=True)
    citation_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, default="document_chunk")
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    locator: Mapped[str | None] = mapped_column(String(256), nullable=True)
    metadata_extra: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("idx_citation_tenant_chunk", "tenant_id", "chunk_id"),
        Index("idx_citation_tenant_code", "tenant_id", "citation_code", unique=True),
    )
