"""Session and message schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class SessionCreateRequest(BaseModel):
    title: str = Field(default="New Session", max_length=256)
    metadata: dict = Field(default_factory=dict)


class SessionResponse(BaseModel):
    id: UUID
    tenant_id: str
    user_id: UUID
    title: str
    status: str
    metadata: dict
    last_message_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ConversationMessageResponse(BaseModel):
    id: UUID
    session_id: UUID
    role: str
    content: str
    token_count: int
    message_index: int
    trace_id: str | None
    metadata: dict
    created_at: datetime
