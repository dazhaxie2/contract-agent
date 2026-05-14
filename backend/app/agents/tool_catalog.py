"""Stable atomic tool catalog grouped by DDD domain."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AtomicToolSpec(BaseModel):
    name: str
    domain: str
    owner_agent: str
    action: str
    mutates_state: bool = False
    description: str
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)


ATOMIC_TOOL_CATALOG: tuple[AtomicToolSpec, ...] = (
    AtomicToolSpec(
        name="document.read",
        domain="contract",
        owner_agent="retrieval",
        action="read",
        description="Read contract metadata, chunks, and selected excerpts.",
        inputs=["doc_id", "document_ids", "tenant_id"],
        outputs=["document", "chunks"],
    ),
    AtomicToolSpec(
        name="clause.extract",
        domain="contract",
        owner_agent="compliance",
        action="analyze",
        description="Extract payment, breach, termination, confidentiality, liability, and dispute clauses.",
        inputs=["contract_text", "review_type"],
        outputs=["clauses"],
    ),
    AtomicToolSpec(
        name="retrieval.search",
        domain="knowledge",
        owner_agent="retrieval",
        action="read",
        description="Search legal, case, policy, and contract references with tenant and document filters.",
        inputs=["query", "tenant_id", "filters"],
        outputs=["references", "retrieval_debug"],
    ),
    AtomicToolSpec(
        name="compliance.review",
        domain="review",
        owner_agent="compliance",
        action="analyze",
        description="Identify legal and contract compliance risks and confidence levels.",
        inputs=["clauses", "references", "review_type"],
        outputs=["risk_items", "overall_risk"],
    ),
    AtomicToolSpec(
        name="drafting.suggest",
        domain="review",
        owner_agent="drafting",
        action="draft",
        description="Generate revision suggestions and replacement clause language.",
        inputs=["risk_items", "contract_context", "references"],
        outputs=["recommendations", "markdown"],
    ),
    AtomicToolSpec(
        name="comparison.compare_versions",
        domain="contract",
        owner_agent="comparison",
        action="analyze",
        description="Compare two contract versions and identify risk-impacting differences.",
        inputs=["base_document_id", "target_document_id", "focus"],
        outputs=["diff_items", "risk_impact"],
    ),
    AtomicToolSpec(
        name="validation.verify",
        domain="observability",
        owner_agent="validation",
        action="validate",
        description="Verify generated legal content against source references and uncertainty rules.",
        inputs=["generated_text", "references"],
        outputs=["verdict", "issues", "corrected_text"],
    ),
    AtomicToolSpec(
        name="feedback.capture",
        domain="observability",
        owner_agent="orchestrator",
        action="write",
        mutates_state=True,
        description="Persist user feedback and create a replayable regression case.",
        inputs=["execution_id", "score", "comment"],
        outputs=["regression_case_id"],
    ),
    AtomicToolSpec(
        name="report.export_markdown",
        domain="review",
        owner_agent="drafting",
        action="export",
        description="Prepare a Markdown report for copy or download.",
        inputs=["review_report", "markdown"],
        outputs=["markdown"],
    ),
)


def tool_catalog_by_domain() -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for item in ATOMIC_TOOL_CATALOG:
        grouped.setdefault(item.domain, []).append(item.model_dump())
    return grouped
