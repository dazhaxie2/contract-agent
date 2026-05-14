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


class PlanStep(BaseModel):
    step_id: str
    title: str
    description: str = ""
    domain: str
    tool: str
    action: str = "read"
    mutates_state: bool = False
    status: str = "pending"


class AgentPlanRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=10000)
    session_id: UUID
    tenant_id: str = Field(..., min_length=1, max_length=64)
    task_type: str = Field(default="contract_review")
    context: dict = Field(default_factory=dict)
    filters: dict = Field(default_factory=dict)


class AgentPlanResponse(BaseModel):
    decision_id: str
    intent_summary: str
    steps: list[PlanStep]
    requires_confirmation: bool
    estimated_changes: list[str] = Field(default_factory=list)
    context: dict = Field(default_factory=dict)
    created_at: datetime
    expires_at: datetime


class AgentDecisionExecuteRequest(BaseModel):
    confirmed: bool = True
    comment: str = ""


class AgentExecuteResponse(BaseModel):
    execution_id: UUID
    trace_id: str
    status: str
    result: str
    references: list[dict] = Field(default_factory=list)
    steps: list[dict] = Field(default_factory=list)
    usage: dict = Field(default_factory=dict)
    latency_ms: float
    review_report: dict | None = None
    decision_id: str | None = None
    plan: dict | None = None
    tool_results: list[dict] = Field(default_factory=list)
    regression_case_id: str | None = None


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
