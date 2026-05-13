"""Agent execution schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AgentExecuteRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=10000)
    task_type: str = Field(default="auto")
    session_id: UUID
    tenant_id: str = Field(..., min_length=1, max_length=64)
    model_config_id: UUID | None = None
    prompt_template_id: UUID | None = None
    stream: bool = False
    filters: dict = Field(default_factory=dict)


class AgentExecuteResponse(BaseModel):
    execution_id: UUID
    trace_id: str
    status: str
    result: str
    references: list[dict] = Field(default_factory=list)
    steps: list[dict] = Field(default_factory=list)
    usage: dict = Field(default_factory=dict)
    latency_ms: float


class AgentStepResponse(BaseModel):
    id: UUID
    step_number: int
    step_type: str
    agent_type: str
    thought: str | None
    action: str | None
    action_input: dict
    observation: str | None
    tool_name: str | None
    tokens_used: int
    latency_ms: float
    status: str
    started_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class AgentExecutionDetail(BaseModel):
    id: UUID
    trace_id: str
    task_type: str
    user_query: str
    parsed_intent: str | None
    agent_type: str
    status: str
    result: str | None
    total_steps: int
    total_tokens_used: int
    latency_ms: float | None
    relevance_score: float | None
    user_feedback: int | None
    steps: list[AgentStepResponse] = Field(default_factory=list)
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}
