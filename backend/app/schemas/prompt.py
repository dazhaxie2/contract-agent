"""提示词管理 Schema"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class PromptVariable(BaseModel):
    name: str
    type: str = "string"  # string/number/boolean/array/object
    description: str = ""
    default_value: str = ""
    required: bool = True


class PromptTemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    display_name: str = Field(..., min_length=1, max_length=256)
    description: str = ""
    category: str = Field(..., pattern="^(system|task|dynamic|evaluation)$")
    task_type: str = ""
    system_prompt: str = ""
    user_prompt_template: str = Field(..., min_length=1)
    variables: list[PromptVariable] = []
    target_model_type: str = ""
    target_agent: str = ""
    output_format: str = "text"
    output_schema: dict | None = None
    validation_rules: list[dict] = []
    tags: list[str] = []


class PromptTemplateUpdate(BaseModel):
    display_name: str | None = None
    description: str | None = None
    system_prompt: str | None = None
    user_prompt_template: str | None = None
    variables: list[PromptVariable] | None = None
    target_model_type: str | None = None
    target_agent: str | None = None
    output_format: str | None = None
    output_schema: dict | None = None
    validation_rules: list[dict] | None = None
    tags: list[str] | None = None
    changelog: str = ""


class PromptTemplateResponse(BaseModel):
    id: UUID
    name: str
    display_name: str
    description: str
    category: str
    task_type: str | None
    system_prompt: str | None
    user_prompt_template: str
    variables: list[dict]
    target_model_type: str | None
    target_agent: str | None
    output_format: str | None
    output_schema: dict | None
    validation_rules: list[dict]
    current_version: int
    status: str
    is_default: bool
    tags: list[str]
    avg_quality_score: float | None
    usage_count: int
    created_at: datetime
    updated_at: datetime
    published_at: datetime | None

    model_config = {"from_attributes": True}


class PromptVersionResponse(BaseModel):
    id: UUID
    template_id: UUID
    version: int
    system_prompt: str | None
    user_prompt_template: str
    variables: list[dict]
    output_format: str | None
    changelog: str | None
    quality_score: float | None
    evaluation_results: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class PromptTestRequest(BaseModel):
    template_id: UUID | None = None
    system_prompt: str = ""
    user_prompt_template: str = ""
    variables: dict = {}
    model_config_id: UUID | None = None
    temperature: float | None = None
    max_tokens: int | None = None


class PromptTestResponse(BaseModel):
    rendered_prompt: str
    output: str
    model: str
    usage: dict
    latency_ms: float
    quality_score: float | None = None
