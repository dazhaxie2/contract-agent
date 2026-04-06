"""文档与文档块模型"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Integer, Float, DateTime, Text, Index, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # 文档基础信息
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    doc_type: Mapped[str] = mapped_column(String(32), nullable=False)  # law/contract/regulation/case/guide
    file_name: Mapped[str] = mapped_column(String(256), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    # 元数据
    issuing_authority: Mapped[str] = mapped_column(String(256), nullable=True)
    effective_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    expiry_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    applicable_industry: Mapped[list] = mapped_column(ARRAY(String), default=list)
    applicable_region: Mapped[list] = mapped_column(ARRAY(String), default=list)
    version: Mapped[str] = mapped_column(String(32), nullable=True)
    keywords: Mapped[list] = mapped_column(ARRAY(String), default=list)
    metadata_extra: Mapped[dict] = mapped_column(JSONB, default=dict)
    # 处理状态
    status: Mapped[str] = mapped_column(String(32), default="uploaded")  # uploaded/processing/processed/failed
    is_effective: Mapped[bool] = mapped_column(Boolean, default=True)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    process_error: Mapped[str] = mapped_column(Text, nullable=True)
    # 上传者
    uploaded_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=True)
    # 时间戳
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        Index("idx_doc_type_status", "doc_type", "status"),
        Index("idx_doc_tenant_type_date", "tenant_id", "doc_type", "effective_date"),
        Index("idx_doc_effective", "is_effective", "effective_date"),
    )


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    doc_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # 块内容
    content: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=True)
    chunk_type: Mapped[str] = mapped_column(String(32), nullable=False)  # structural/semantic/summary/table
    # 层级结构
    parent_chunk_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=True)
    hierarchy_path: Mapped[str] = mapped_column(String(512), nullable=True)  # 章>节>条>款
    hierarchy_level: Mapped[int] = mapped_column(Integer, default=0)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    # 元数据
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    legal_priority: Mapped[int] = mapped_column(Integer, default=0)  # 法律效力优先级
    entity_tags: Mapped[list] = mapped_column(ARRAY(String), default=list)
    metadata_extra: Mapped[dict] = mapped_column(JSONB, default=dict)
    # 向量状态
    vector_status: Mapped[str] = mapped_column(String(32), default="pending")  # pending/indexed/failed
    graph_status: Mapped[str] = mapped_column(String(32), default="pending")
    # 时间戳
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("idx_chunk_doc_index", "doc_id", "chunk_index"),
        Index("idx_chunk_hierarchy", "doc_id", "hierarchy_path"),
        Index("idx_chunk_tenant_type", "tenant_id", "chunk_type"),
    )
