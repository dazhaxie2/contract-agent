"""Agent执行链路模型 - 支持全链路追踪"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Integer, Float, DateTime, Text, Index, JSON, Uuid, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AgentExecution(Base):
    """Agent执行记录表"""
    __tablename__ = "agent_executions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trace_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    session_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=True, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # 任务信息
    task_type: Mapped[str] = mapped_column(String(64), nullable=False)
    user_query: Mapped[str] = mapped_column(Text, nullable=False)
    parsed_intent: Mapped[str] = mapped_column(String(128), nullable=True)
    parsed_entities: Mapped[list] = mapped_column(JSON, default=list)
    # 执行信息
    agent_type: Mapped[str] = mapped_column(String(64), nullable=False)  # master/document/retrieval/compliance/...
    model_config_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=True)
    prompt_template_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=True)
    total_steps: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    total_cost: Mapped[float] = mapped_column(Float, default=0.0)
    # 结果
    status: Mapped[str] = mapped_column(String(32), default="running")
    result: Mapped[str] = mapped_column(Text, nullable=True)
    result_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    # 质量指标
    relevance_score: Mapped[float] = mapped_column(Float, nullable=True)
    factuality_score: Mapped[float] = mapped_column(Float, nullable=True)
    user_feedback: Mapped[int] = mapped_column(Integer, nullable=True)  # 1-5
    # 性能
    latency_ms: Mapped[float] = mapped_column(Float, nullable=True)
    retrieval_latency_ms: Mapped[float] = mapped_column(Float, nullable=True)
    generation_latency_ms: Mapped[float] = mapped_column(Float, nullable=True)
    # 时间
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_exec_tenant_status", "tenant_id", "status"),
        Index("idx_exec_user_time", "user_id", "created_at"),
        Index("idx_exec_task_type", "task_type", "created_at"),
    )


class AgentDecision(Base):
    """Persisted plan/confirmation record for Plan -> Confirm -> Execute."""

    __tablename__ = "agent_decisions"

    decision_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    session_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    task_type: Mapped[str] = mapped_column(String(64), nullable=False, default="contract_review")
    query: Mapped[str] = mapped_column(Text, nullable=False)
    filters: Mapped[dict] = mapped_column(JSON, default=dict)
    intent_summary: Mapped[str] = mapped_column(Text, nullable=False)
    steps: Mapped[list] = mapped_column(JSON, default=list)
    requires_confirmation: Mapped[bool] = mapped_column(Boolean, default=True)
    estimated_changes: Mapped[list] = mapped_column(JSON, default=list)
    context: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="planned")
    user_confirmation: Mapped[dict] = mapped_column(JSON, default=dict)
    execution_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=True, index=True)
    trace_id: Mapped[str] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        Index("idx_decision_tenant_status", "tenant_id", "status"),
        Index("idx_decision_user_time", "user_id", "created_at"),
        Index("idx_decision_expires", "expires_at"),
    )


class AgentStep(Base):
    """Agent执行步骤表 - ReAct Thought/Action/Observation"""
    __tablename__ = "agent_steps"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    execution_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    trace_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    span_id: Mapped[str] = mapped_column(String(64), nullable=False)
    parent_span_id: Mapped[str] = mapped_column(String(64), nullable=True)
    # 步骤信息
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    step_type: Mapped[str] = mapped_column(String(32), nullable=False)  # thought/action/observation/validation
    agent_type: Mapped[str] = mapped_column(String(64), nullable=False)
    # 内容
    thought: Mapped[str] = mapped_column(Text, nullable=True)
    action: Mapped[str] = mapped_column(String(128), nullable=True)
    action_input: Mapped[dict] = mapped_column(JSON, default=dict)
    observation: Mapped[str] = mapped_column(Text, nullable=True)
    # 工具调用
    tool_name: Mapped[str] = mapped_column(String(64), nullable=True)
    tool_input: Mapped[dict] = mapped_column(JSON, default=dict)
    tool_output: Mapped[str] = mapped_column(Text, nullable=True)
    # 检索信息
    retrieved_chunks: Mapped[list] = mapped_column(JSON, default=list)
    retrieval_scores: Mapped[list] = mapped_column(JSON, default=list)
    # 性能
    tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="running")
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    # 时间
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_step_execution", "execution_id", "step_number"),
    )
