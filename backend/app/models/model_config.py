"""模型配置与部署模型 - 支持可视化管理"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Integer, Float, DateTime, Text, Boolean, Index, JSON, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ModelConfig(Base):
    """模型配置表 - 管理所有大模型/小模型配置"""
    __tablename__ = "model_configs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # 基础信息
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    display_name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    model_type: Mapped[str] = mapped_column(String(32), nullable=False)  # generation/embedding/reranker/light
    provider: Mapped[str] = mapped_column(String(32), nullable=False)  # aliyun/openai/local/vllm
    model_id: Mapped[str] = mapped_column(String(128), nullable=False)  # qwen-max / text-embedding-v3
    # 模型参数
    temperature: Mapped[float] = mapped_column(Float, default=0.1)
    top_p: Mapped[float] = mapped_column(Float, default=0.8)
    max_tokens: Mapped[int] = mapped_column(Integer, default=8192)
    frequency_penalty: Mapped[float] = mapped_column(Float, default=0.0)
    presence_penalty: Mapped[float] = mapped_column(Float, default=0.0)
    stop_sequences: Mapped[list] = mapped_column(JSON, default=list)
    # 高级参数
    context_window: Mapped[int] = mapped_column(Integer, default=32768)
    supports_function_calling: Mapped[bool] = mapped_column(Boolean, default=False)
    supports_streaming: Mapped[bool] = mapped_column(Boolean, default=True)
    # 性能参数
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=120)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    max_concurrent_requests: Mapped[int] = mapped_column(Integer, default=50)
    requests_per_minute: Mapped[int] = mapped_column(Integer, default=600)
    # 端点配置
    api_endpoint: Mapped[str] = mapped_column(String(512), nullable=True)
    api_key_encrypted: Mapped[str] = mapped_column(String(1024), nullable=True)
    extra_headers: Mapped[dict] = mapped_column(JSON, default=dict)
    # 状态
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    # 评估指标
    avg_latency_ms: Mapped[float] = mapped_column(Float, nullable=True)
    avg_tokens_per_second: Mapped[float] = mapped_column(Float, nullable=True)
    error_rate: Mapped[float] = mapped_column(Float, nullable=True)
    quality_score: Mapped[float] = mapped_column(Float, nullable=True)
    # 额外配置
    extra_config: Mapped[dict] = mapped_column(JSON, default=dict)
    # 元数据
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        Index("idx_model_tenant_type", "tenant_id", "model_type"),
        Index("idx_model_provider_active", "provider", "is_active"),
    )


class ModelDeployment(Base):
    """模型部署记录表"""
    __tablename__ = "model_deployments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_config_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # 部署信息
    deployment_name: Mapped[str] = mapped_column(String(128), nullable=False)
    deployment_type: Mapped[str] = mapped_column(String(32), nullable=False)  # cloud_api/vllm/triton/onnx
    endpoint_url: Mapped[str] = mapped_column(String(512), nullable=True)
    replicas: Mapped[int] = mapped_column(Integer, default=1)
    gpu_type: Mapped[str] = mapped_column(String(32), nullable=True)  # A100/T4/V100
    gpu_count: Mapped[int] = mapped_column(Integer, default=0)
    # 资源配额
    cpu_limit: Mapped[str] = mapped_column(String(16), nullable=True)
    memory_limit: Mapped[str] = mapped_column(String(16), nullable=True)
    # 状态
    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending/deploying/running/stopped/failed
    health_status: Mapped[str] = mapped_column(String(32), default="unknown")
    # 性能指标
    current_qps: Mapped[float] = mapped_column(Float, default=0.0)
    max_qps: Mapped[float] = mapped_column(Float, default=0.0)
    avg_latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    p99_latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    # 元数据
    deploy_config: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )


class ABTest(Base):
    """A/B测试配置表"""
    __tablename__ = "ab_tests"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    test_type: Mapped[str] = mapped_column(String(32), nullable=False)  # model/prompt/retrieval/rerank
    # 实验组配置
    control_config_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    treatment_config_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    traffic_split: Mapped[float] = mapped_column(Float, default=0.1)  # treatment组流量比例
    # 评估指标
    primary_metric: Mapped[str] = mapped_column(String(64), nullable=False)  # recall/precision/latency/quality
    metrics_config: Mapped[dict] = mapped_column(JSON, default=dict)
    # 结果
    control_metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    treatment_metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    winner: Mapped[str] = mapped_column(String(16), nullable=True)  # control/treatment/inconclusive
    # 状态
    status: Mapped[str] = mapped_column(String(32), default="draft")  # draft/running/completed/cancelled
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
