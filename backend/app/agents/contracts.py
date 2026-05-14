"""Shared input/output contracts for specialized sub-agents."""

from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


SUB_AGENT_SCHEMA_VERSION = "2026-05-14"
SubAgentType = Literal["retrieval", "compliance", "comparison", "drafting", "legal_search", "validation"]


class SubAgentContractSpec(BaseModel):
    agent_type: SubAgentType
    domain: str
    purpose: str
    required_context: list[str] = Field(default_factory=list)
    expected_outputs: list[str] = Field(default_factory=list)
    allowed_tools: list[str] = Field(default_factory=list)


class SubAgentReference(BaseModel):
    citation_id: str | None = None
    citation_code: str | None = None
    document_id: str | None = None
    doc_title: str | None = None
    chunk_id: str | None = None
    locator: str | None = None
    excerpt: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SubAgentFinding(BaseModel):
    title: str
    severity: str = "medium"
    summary: str = ""
    recommendation: str = ""
    confidence: float = 0.5
    references: list[SubAgentReference] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SubAgentTaskInput(BaseModel):
    model_config = ConfigDict(extra="allow")

    schema_version: str = SUB_AGENT_SCHEMA_VERSION
    task_id: str = Field(default_factory=lambda: f"task_{uuid.uuid4().hex[:16]}")
    agent_type: SubAgentType
    task_description: str
    tenant_id: str = "default"
    session_id: str | None = None
    decision_id: str | None = None
    document_ids: list[str] = Field(default_factory=list)
    filters: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)
    references: list[SubAgentReference] = Field(default_factory=list)
    expected_output: dict[str, Any] = Field(default_factory=dict)


class SubAgentToolResult(BaseModel):
    step_number: int | None = None
    step_type: str | None = None
    tool_name: str | None = None
    status: str = "completed"
    latency_ms: float = 0.0
    tokens_used: int = 0
    observation: str = ""


class SubAgentTaskOutput(BaseModel):
    schema_version: str = SUB_AGENT_SCHEMA_VERSION
    task_id: str
    agent_type: SubAgentType
    success: bool
    answer: str
    findings: list[SubAgentFinding] = Field(default_factory=list)
    references: list[SubAgentReference] = Field(default_factory=list)
    tool_results: list[SubAgentToolResult] = Field(default_factory=list)
    usage: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


SUB_AGENT_CONTRACTS: dict[str, SubAgentContractSpec] = {
    "retrieval": SubAgentContractSpec(
        agent_type="retrieval",
        domain="knowledge",
        purpose="Find grounded legal, case, policy, and contract references.",
        required_context=["tenant_id", "query", "filters"],
        expected_outputs=["answer", "references", "tool_results"],
        allowed_tools=["search_knowledge_base", "expand_search_query"],
    ),
    "compliance": SubAgentContractSpec(
        agent_type="compliance",
        domain="review",
        purpose="Identify contract compliance risks and legal basis.",
        required_context=["tenant_id", "task_description", "references"],
        expected_outputs=["answer", "findings", "references", "tool_results"],
        allowed_tools=["compliance_check", "score_risk"],
    ),
    "comparison": SubAgentContractSpec(
        agent_type="comparison",
        domain="contract",
        purpose="Compare contract versions and risk-impacting changes.",
        required_context=["tenant_id", "document_ids"],
        expected_outputs=["answer", "findings", "tool_results"],
        allowed_tools=["compare_clauses"],
    ),
    "drafting": SubAgentContractSpec(
        agent_type="drafting",
        domain="review",
        purpose="Draft or optimize contract clauses.",
        required_context=["tenant_id", "task_description", "references"],
        expected_outputs=["answer", "findings", "references", "tool_results"],
        allowed_tools=["draft_clause", "optimize_clause"],
    ),
    "legal_search": SubAgentContractSpec(
        agent_type="legal_search",
        domain="knowledge",
        purpose="Search specific legal provisions and perform deterministic legal calculations.",
        required_context=["tenant_id", "task_description"],
        expected_outputs=["answer", "references", "tool_results"],
        allowed_tools=["search_law", "calculate"],
    ),
    "validation": SubAgentContractSpec(
        agent_type="validation",
        domain="observability",
        purpose="Verify factuality, citation grounding, and compliance of generated legal content.",
        required_context=["tenant_id", "task_description", "references"],
        expected_outputs=["answer", "findings", "tool_results"],
        allowed_tools=["factuality_check", "compliance_validation"],
    ),
}


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple | set):
        return list(value)
    return [value]


def _document_ids(context: dict[str, Any], filters: dict[str, Any]) -> list[str]:
    values: list[Any] = []
    values.extend(_as_list(context.get("document_ids")))
    values.extend(_as_list(filters.get("document_ids")))
    for key in ("doc_id", "document_id"):
        if context.get(key):
            values.append(context[key])
        if filters.get(key):
            values.append(filters[key])

    seen: set[str] = set()
    normalized: list[str] = []
    for value in values:
        text = str(value)
        if text and text not in seen:
            seen.add(text)
            normalized.append(text)
    return normalized


def _references(context: dict[str, Any]) -> list[SubAgentReference]:
    raw_refs = context.get("references") or context.get("context_refs") or []
    references: list[SubAgentReference] = []
    for item in _as_list(raw_refs):
        if not isinstance(item, dict):
            continue
        references.append(
            SubAgentReference(
                citation_id=_to_optional_str(item.get("citation_id")),
                citation_code=_to_optional_str(item.get("citation_code")),
                document_id=_to_optional_str(item.get("document_id") or item.get("doc_id")),
                doc_title=_to_optional_str(item.get("doc_title") or item.get("title")),
                chunk_id=_to_optional_str(item.get("chunk_id")),
                locator=_to_optional_str(item.get("locator") or item.get("hierarchy")),
                excerpt=_to_optional_str(item.get("excerpt") or item.get("content")),
                metadata=dict(item.get("metadata") or {}),
            )
        )
    return references


def _to_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def build_sub_agent_input(
    *,
    agent_type: str,
    task_description: str,
    context_payload: dict[str, Any] | None = None,
    fallback_tenant_id: str = "default",
) -> SubAgentTaskInput:
    context = dict(context_payload or {})
    filters = dict(context.get("filters") or {})
    tenant_id = str(context.get("tenant_id") or fallback_tenant_id or "default")
    spec = SUB_AGENT_CONTRACTS.get(agent_type)
    expected_output = {
        "domain": spec.domain if spec else "unknown",
        "expected_outputs": spec.expected_outputs if spec else ["answer", "tool_results"],
        "schema_version": SUB_AGENT_SCHEMA_VERSION,
    }

    return SubAgentTaskInput(
        agent_type=agent_type,  # type: ignore[arg-type]
        task_description=task_description,
        tenant_id=tenant_id,
        session_id=_to_optional_str(context.get("session_id")),
        decision_id=_to_optional_str(context.get("decision_id")),
        document_ids=_document_ids(context, filters),
        filters=filters,
        context=context,
        references=_references(context),
        expected_output=expected_output,
    )


def _step_to_tool_result(step: Any, step_number: int) -> SubAgentToolResult:
    step_type = getattr(getattr(step, "step_type", None), "value", None) or str(getattr(step, "step_type", "") or "")
    return SubAgentToolResult(
        step_number=step_number,
        step_type=step_type or None,
        tool_name=getattr(step, "tool_name", None) or getattr(step, "action", None),
        latency_ms=float(getattr(step, "latency_ms", 0.0) or 0.0),
        tokens_used=int(getattr(step, "tokens_used", 0) or 0),
        observation=(getattr(step, "observation", None) or getattr(step, "content", "") or "")[:1000],
    )


def _severity_from_answer(answer: str) -> str:
    lowered = answer.lower()
    if any(marker in answer for marker in ["高风险", "严重", "重大"]) or any(
        marker in lowered for marker in ["high", "critical", "severe"]
    ):
        return "high"
    if any(marker in answer for marker in ["低风险", "轻微"]) or "low" in lowered:
        return "low"
    if any(marker in answer for marker in ["不确定", "依据不足"]) or "uncertain" in lowered:
        return "uncertain"
    return "medium"


def _summary(answer: str, limit: int = 280) -> str:
    text = " ".join((answer or "").strip().split())
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def build_sub_agent_output(task_input: SubAgentTaskInput, result: Any) -> SubAgentTaskOutput:
    answer = str(getattr(result, "output", "") or "")
    steps = list(getattr(result, "steps", []) or [])
    references = task_input.references
    findings: list[SubAgentFinding] = []
    if answer and task_input.agent_type in {"compliance", "comparison", "drafting", "validation"}:
        findings.append(
            SubAgentFinding(
                title=f"{task_input.agent_type} result",
                severity=_severity_from_answer(answer),
                summary=_summary(answer),
                recommendation="See answer for detailed recommendations.",
                confidence=0.72 if references else 0.45,
                references=references[:8],
            )
        )

    return SubAgentTaskOutput(
        task_id=task_input.task_id,
        agent_type=task_input.agent_type,
        success=bool(getattr(result, "success", False)),
        answer=answer,
        findings=findings,
        references=references,
        tool_results=[_step_to_tool_result(step, idx + 1) for idx, step in enumerate(steps)],
        usage={
            "total_tokens": int(getattr(result, "total_tokens", 0) or 0),
            "total_steps": len(steps),
        },
        metadata={
            "input_contract": task_input.model_dump(mode="json"),
            "agent_metadata": dict(getattr(result, "metadata", {}) or {}),
        },
    )
