"""模型配置 Schema"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ModelConfigCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    display_name: str = Field(..., min_length=1, max_length=256)
    description: str = ""
    model_type: str = Field(..., pattern="^(generation|embedding|reranker|light)$")
    provider: str = Field(..., pattern="^(aliyun|openai|local|vllm)$")
    model_id: str = Field(..., min_length=1, max_length=128)
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    top_p: float = Field(default=0.8, ge=0.0, le=1.0)
    max_tokens: int = Field(default=8192, ge=1, le=1000000)
    frequency_penalty: float = Field(default=0.0, ge=-2.0, le=2.0)
    presence_penalty: float = Field(default=0.0, ge=-2.0, le=2.0)
    stop_sequences: list[str] = []
    context_window: int = Field(default=32768, ge=1024)
    supports_function_calling: bool = False
    supports_streaming: bool = True
    timeout_seconds: int = Field(default=120, ge=1, le=600)
    max_retries: int = Field(default=3, ge=0, le=10)
    max_concurrent_requests: int = Field(default=50, ge=1)
    requests_per_minute: int = Field(default=600, ge=1)
    api_endpoint: str = ""
    api_key: str = ""
    extra_headers: dict = {}
    extra_config: dict = {}


class ModelConfigUpdate(BaseModel):
    display_name: str | None = None
    description: str | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)
    max_tokens: int | None = Field(default=None, ge=1)
    frequency_penalty: float | None = None
    presence_penalty: float | None = None
    stop_sequences: list[str] | None = None
    context_window: int | None = None
    supports_function_calling: bool | None = None
    supports_streaming: bool | None = None
    timeout_seconds: int | None = None
    max_retries: int | None = None
    max_concurrent_requests: int | None = None
    requests_per_minute: int | None = None
    api_endpoint: str | None = None
    api_key: str | None = None
    extra_headers: dict | None = None
    extra_config: dict | None = None
    is_active: bool | None = None
    is_default: bool | None = None


class ModelConfigResponse(BaseModel):
    id: UUID
    name: str
    display_name: str
    description: str
    model_type: str
    provider: str
    model_id: str
    temperature: float
    top_p: float
    max_tokens: int
    frequency_penalty: float
    presence_penalty: float
    stop_sequences: list[str]
    context_window: int
    supports_function_calling: bool
    supports_streaming: bool
    timeout_seconds: int
    max_retries: int
    max_concurrent_requests: int
    requests_per_minute: int
    api_endpoint: str | None
    extra_headers: dict
    is_active: bool
    is_default: bool
    version: int
    avg_latency_ms: float | None
    avg_tokens_per_second: float | None
    error_rate: float | None
    quality_score: float | None
    extra_config: dict
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ModelDeploymentCreate(BaseModel):
    model_config_id: UUID
    deployment_name: str
    deployment_type: str = Field(..., pattern="^(cloud_api|vllm|triton|onnx)$")
    endpoint_url: str = ""
    replicas: int = Field(default=1, ge=1, le=100)
    gpu_type: str = ""
    gpu_count: int = Field(default=0, ge=0)
    cpu_limit: str = ""
    memory_limit: str = ""
    deploy_config: dict = {}


class ModelDeploymentResponse(BaseModel):
    id: UUID
    model_config_id: UUID
    deployment_name: str
    deployment_type: str
    endpoint_url: str | None
    replicas: int
    gpu_type: str | None
    gpu_count: int
    status: str
    health_status: str
    current_qps: float
    max_qps: float
    avg_latency_ms: float
    p99_latency_ms: float
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ABTestCreate(BaseModel):
    name: str
    description: str = ""
    test_type: str = Field(..., pattern="^(model|prompt|retrieval|rerank)$")
    control_config_id: UUID
    treatment_config_id: UUID
    traffic_split: float = Field(default=0.1, ge=0.01, le=0.5)
    primary_metric: str


class ABTestResponse(BaseModel):
    id: UUID
    name: str
    description: str
    test_type: str
    control_config_id: UUID
    treatment_config_id: UUID
    traffic_split: float
    primary_metric: str
    control_metrics: dict
    treatment_metrics: dict
    winner: str | None
    status: str
    started_at: datetime | None
    ended_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
