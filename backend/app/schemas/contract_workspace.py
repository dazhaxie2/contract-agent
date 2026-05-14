"""Reserved extension schemas for contract matters, performance events, and expense evidence."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ContractMatter(BaseModel):
    matter_id: str = Field(..., description="External matter identifier")
    tenant_id: str = "default"
    document_id: UUID | None = None
    title: str
    matter_type: Literal["contract_review", "performance", "renewal", "dispute", "expense"] = "performance"
    status: Literal["open", "in_progress", "blocked", "closed"] = "open"
    owner_user_id: UUID | None = None
    due_at: datetime | None = None
    metadata: dict = Field(default_factory=dict)


class PerformanceEvent(BaseModel):
    event_id: str = Field(..., description="External performance event identifier")
    matter_id: str
    document_id: UUID | None = None
    event_type: Literal["delivery", "acceptance", "payment", "invoice", "notice", "termination", "other"]
    occurred_at: datetime | None = None
    description: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class ExpenseEvidence(BaseModel):
    evidence_id: str = Field(..., description="External evidence identifier")
    matter_id: str | None = None
    event_id: str | None = None
    evidence_type: Literal["invoice", "receipt", "bank_slip", "delivery_note", "email", "other"] = "invoice"
    amount: float | None = None
    currency: str = "CNY"
    file_document_id: UUID | None = None
    description: str = ""
    metadata: dict = Field(default_factory=dict)
