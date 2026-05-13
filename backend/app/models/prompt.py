"""提示词模板管理模型 - 支持可视化管理与版本控制"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Integer, Float, DateTime, Text, Boolean, Index, JSON, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PromptTemplate(Base):
    """提示词模板表"""
    __tablename__ = "prompt_templates"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # 基础信息
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    display_name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(32), nullable=False)  # system/task/dynamic/evaluation
    task_type: Mapped[str] = mapped_column(String(64), nullable=True)
    # 提示词内容
    system_prompt: Mapped[str] = mapped_column(Text, nullable=True)
    user_prompt_template: Mapped[str] = mapped_column(Text, nullable=False)
    # 变量定义
    variables: Mapped[list] = mapped_column(JSON, default=list)
    # 关联配置
    target_model_type: Mapped[str] = mapped_column(String(32), nullable=True)  # generation/light
    target_agent: Mapped[str] = mapped_column(String(64), nullable=True)
    # 约束规则
    output_format: Mapped[str] = mapped_column(String(32), nullable=True)  # json/markdown/text/structured
    output_schema: Mapped[dict] = mapped_column(JSON, nullable=True)
    validation_rules: Mapped[list] = mapped_column(JSON, default=list)
    # 版本与状态
    current_version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(32), default="draft")  # draft/published/deprecated
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    # 标签
    tags: Mapped[list] = mapped_column(JSON, default=list)
    # 评估指标
    avg_quality_score: Mapped[float] = mapped_column(Float, nullable=True)
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    # 审计
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=True)
    published_by: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_prompt_tenant_category", "tenant_id", "category"),
        Index("idx_prompt_task_type", "task_type", "status"),
        Index("idx_prompt_agent", "target_agent", "status"),
    )


class PromptVersion(Base):
    """提示词版本历史表"""
    __tablename__ = "prompt_versions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    # 版本内容快照
    system_prompt: Mapped[str] = mapped_column(Text, nullable=True)
    user_prompt_template: Mapped[str] = mapped_column(Text, nullable=False)
    variables: Mapped[list] = mapped_column(JSON, default=list)
    output_format: Mapped[str] = mapped_column(String(32), nullable=True)
    output_schema: Mapped[dict] = mapped_column(JSON, nullable=True)
    validation_rules: Mapped[list] = mapped_column(JSON, default=list)
    # 变更说明
    changelog: Mapped[str] = mapped_column(Text, nullable=True)
    # 评估结果
    evaluation_results: Mapped[dict] = mapped_column(JSON, default=dict)
    quality_score: Mapped[float] = mapped_column(Float, nullable=True)
    # 审计
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("idx_prompt_version_template", "template_id", "version", unique=True),
    )
