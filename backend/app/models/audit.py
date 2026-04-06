"""审计日志模型"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, Text, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trace_id: Mapped[str] = mapped_column(String(64), nullable=True, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # 操作信息
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(128), nullable=True)
    # 详情
    request_method: Mapped[str] = mapped_column(String(10), nullable=True)
    request_path: Mapped[str] = mapped_column(String(512), nullable=True)
    request_body: Mapped[dict] = mapped_column(JSONB, nullable=True)
    response_status: Mapped[int] = mapped_column(nullable=True)
    # 变更记录
    old_value: Mapped[dict] = mapped_column(JSONB, nullable=True)
    new_value: Mapped[dict] = mapped_column(JSONB, nullable=True)
    # 客户端信息
    ip_address: Mapped[str] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str] = mapped_column(String(512), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("idx_audit_tenant_time", "tenant_id", "created_at"),
        Index("idx_audit_action_resource", "action", "resource_type"),
        Index("idx_audit_user_time", "user_id", "created_at"),
    )
